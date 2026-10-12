"""Админка: ученики и ручные доступы, домашние задания (PDF) и уроки (ссылки на записи)."""
import json
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import files
from .access import drop_item, item_users, set_item_users, set_user_grants, user_grants
from .db import get_db
from .models import GRANT_KINDS, Grant, Homework, Lesson, User, Visualization
from .routes_auth import check_password_rules
from .security import hash_password, require_admin
from .serialize import hw_out, lesson_out, user_out

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

KIND_MODEL = {"viz": Visualization, "hw": Homework, "lesson": Lesson}


class GrantsIn(BaseModel):
    viz: Optional[List[int]] = None
    hw: Optional[List[int]] = None
    lesson: Optional[List[int]] = None


class UsersIn(BaseModel):
    user_ids: List[int]


class PasswordIn(BaseModel):
    password: str


class LessonIn(BaseModel):
    number: Optional[int] = None
    title: Optional[str] = None
    url: Optional[str] = None
    user_ids: Optional[List[int]] = None


# ── Помощники ──
def _existing_ids(db: Session, model, ids: List[int]) -> List[int]:
    ids = list(set(ids))
    if not ids:
        return []
    found = set(db.scalars(select(model.id).where(model.id.in_(ids))))
    if found != set(ids):
        raise HTTPException(400, "Часть материалов или учеников не найдена. Обновите страницу.")
    return ids


def _user(db: Session, pk: int) -> User:
    u = db.get(User, pk)
    if not u:
        raise HTTPException(404, "Ученик не найден.")
    return u


def _number(value, what: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"Номер {what} — целое число.")
    if not 1 <= n <= 100000:
        raise HTTPException(400, f"Номер {what} — от 1 до 100000.")
    return n


def _title(value: Optional[str]) -> str:
    v = (value or "").strip()
    if len(v) > 200:
        raise HTTPException(400, "Название длиннее 200 символов.")
    return v


def _url(value: Optional[str]) -> str:
    v = (value or "").strip()
    p = urlparse(v)
    if p.scheme not in ("http", "https") or not p.netloc or len(v) > 1000:
        raise HTTPException(400, "Ссылка на урок должна начинаться с https:// (или http://).")
    return v


def _parse_user_ids(raw: Optional[str]) -> Optional[List[int]]:
    """user_ids в форме приходят строкой JSON: «[1, 4, 7]»."""
    if raw is None or raw == "":
        return None
    try:
        data = json.loads(raw)
        return [int(x) for x in data]
    except (ValueError, TypeError):
        raise HTTPException(400, "Список учеников передан в неверном виде.")


# ── Ученики ──
@router.get("/users")
def users_list(db: Session = Depends(get_db)):
    grants = user_grants(db)
    users = db.scalars(select(User).order_by(User.nickname_key)).all()
    return {"users": [user_out(u, grants.get(u.id)) for u in users]}


@router.put("/users/{pk}/grants")
def users_set_grants(pk: int, body: GrantsIn, db: Session = Depends(get_db)):
    """Заменить доступы ученика. Передаются только те виды, которые меняются."""
    u = _user(db, pk)
    for kind in GRANT_KINDS:
        ids = getattr(body, kind)
        if ids is not None:
            set_user_grants(db, u.id, kind, _existing_ids(db, KIND_MODEL[kind], ids))
    db.commit()
    return user_out(u, user_grants(db).get(u.id))


@router.post("/users/{pk}/password")
def users_reset_password(pk: int, body: PasswordIn, db: Session = Depends(get_db)):
    """Новый пароль от админа (восстановления по почте нет). Старые входы ученика сбрасываются."""
    u = _user(db, pk)
    check_password_rules(body.password)
    u.password_hash = hash_password(body.password)
    u.session_version = (u.session_version or 1) + 1
    db.commit()
    return {"ok": True}


@router.delete("/users/{pk}")
def users_delete(pk: int, db: Session = Depends(get_db)):
    u = _user(db, pk)
    for g in db.scalars(select(Grant).where(Grant.user_id == u.id)).all():
        db.delete(g)
    db.delete(u)
    db.commit()
    return {"ok": True}


# ── Доступ к одному материалу: кому открыт ──
@router.put("/access/{kind}/{item_id}")
def access_set(kind: str, item_id: int, body: UsersIn, db: Session = Depends(get_db)):
    if kind not in KIND_MODEL:
        raise HTTPException(404)
    if not db.get(KIND_MODEL[kind], item_id):
        raise HTTPException(404, "Материал не найден.")
    set_item_users(db, kind, item_id, _existing_ids(db, User, body.user_ids))
    db.commit()
    return {"user_ids": sorted(item_users(db, kind).get(item_id, []))}


# ── Домашние задания ──
def _hw_all(db: Session) -> Dict[str, list]:
    who = item_users(db, "hw")
    return {"items": [hw_out(h, who.get(h.id, [])) for h in db.scalars(select(Homework).order_by(Homework.number.desc()))]}


def _hw_number_free(db: Session, number: int, pk: Optional[int] = None) -> None:
    q = select(Homework.id).where(Homework.number == number)
    if pk is not None:
        q = q.where(Homework.id != pk)
    if db.scalar(q):
        raise HTTPException(409, f"ДЗ № {number} уже есть. Измените его или выберите другой номер.")


@router.get("/homeworks")
def hw_list(db: Session = Depends(get_db)):
    return _hw_all(db)


@router.post("/homeworks", status_code=201)
async def hw_create(
    number: str = Form(...), title: str = Form(""), user_ids: Optional[str] = Form(None),
    pdf: UploadFile = File(...), db: Session = Depends(get_db),
):
    n = _number(number, "ДЗ")
    _hw_number_free(db, n)
    ids = _parse_user_ids(user_ids)
    file_name = await files.save_hw_pdf(n, pdf)
    h = Homework(number=n, title=_title(title), file_name=file_name)
    db.add(h)
    db.flush()
    if ids:
        set_item_users(db, "hw", h.id, _existing_ids(db, User, ids))
    db.commit()
    return hw_out(h, item_users(db, "hw").get(h.id, []))


@router.patch("/homeworks/{pk}")
async def hw_update(
    pk: int, number: Optional[str] = Form(None), title: Optional[str] = Form(None),
    user_ids: Optional[str] = Form(None), pdf: Optional[UploadFile] = File(None), db: Session = Depends(get_db),
):
    h = db.get(Homework, pk)
    if not h:
        raise HTTPException(404, "Задание не найдено.")
    if number is not None:
        n = _number(number, "ДЗ")
        _hw_number_free(db, n, h.id)
        h.number = n
    if title is not None:
        h.title = _title(title)
    if pdf is not None and pdf.filename:
        new_name = await files.save_hw_pdf(h.number, pdf)
        if new_name != h.file_name:
            files.delete_hw(h.file_name)
        h.file_name = new_name
    ids = _parse_user_ids(user_ids)
    if ids is not None:
        set_item_users(db, "hw", h.id, _existing_ids(db, User, ids))
    db.commit()
    return hw_out(h, item_users(db, "hw").get(h.id, []))


@router.delete("/homeworks/{pk}")
def hw_delete(pk: int, db: Session = Depends(get_db)):
    h = db.get(Homework, pk)
    if not h:
        raise HTTPException(404, "Задание не найдено.")
    files.delete_hw(h.file_name)
    drop_item(db, "hw", h.id)
    db.delete(h)
    db.commit()
    return {"ok": True}


# ── Уроки ──
def _lesson_number_free(db: Session, number: int, pk: Optional[int] = None) -> None:
    q = select(Lesson.id).where(Lesson.number == number)
    if pk is not None:
        q = q.where(Lesson.id != pk)
    if db.scalar(q):
        raise HTTPException(409, f"Урок № {number} уже есть. Измените его или выберите другой номер.")


@router.get("/lessons")
def lessons_list(db: Session = Depends(get_db)):
    who = item_users(db, "lesson")
    return {"items": [lesson_out(l, who.get(l.id, [])) for l in db.scalars(select(Lesson).order_by(Lesson.number.desc()))]}


@router.post("/lessons", status_code=201)
def lessons_create(body: LessonIn, db: Session = Depends(get_db)):
    n = _number(body.number, "урока")
    _lesson_number_free(db, n)
    l = Lesson(number=n, title=_title(body.title), url=_url(body.url))
    db.add(l)
    db.flush()
    if body.user_ids:
        set_item_users(db, "lesson", l.id, _existing_ids(db, User, body.user_ids))
    db.commit()
    return lesson_out(l, item_users(db, "lesson").get(l.id, []))


@router.patch("/lessons/{pk}")
def lessons_update(pk: int, body: LessonIn, db: Session = Depends(get_db)):
    l = db.get(Lesson, pk)
    if not l:
        raise HTTPException(404, "Урок не найден.")
    if body.number is not None:
        n = _number(body.number, "урока")
        _lesson_number_free(db, n, l.id)
        l.number = n
    if body.title is not None:
        l.title = _title(body.title)
    if body.url is not None:
        l.url = _url(body.url)
    if body.user_ids is not None:
        set_item_users(db, "lesson", l.id, _existing_ids(db, User, body.user_ids))
    db.commit()
    return lesson_out(l, item_users(db, "lesson").get(l.id, []))


@router.delete("/lessons/{pk}")
def lessons_delete(pk: int, db: Session = Depends(get_db)):
    l = db.get(Lesson, pk)
    if not l:
        raise HTTPException(404, "Урок не найден.")
    drop_item(db, "lesson", l.id)
    db.delete(l)
    db.commit()
    return {"ok": True}
