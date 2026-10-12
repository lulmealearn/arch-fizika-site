"""Ученики: регистрация, вход, выход и «мои материалы» для личного кабинета."""
import re
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import config
from .access import current_user, granted_ids
from .tracking import touch
from .db import get_db
from .models import Grant, Lesson, LessonProgress, LessonViz, Mock, MockProgress, Report, User, Visualization
from .security import (USER_COOKIE, USER_SESSION_DAYS, check_same_origin, hash_password, is_admin, make_user_token,
                       register_limit, user_login_limit, verify_password)
from .serialize import lesson_files, mock_out, report_out, viz_public

router = APIRouter(prefix="/api")

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.\-]{3,32}$")
PASSWORD_MIN, PASSWORD_MAX = 6, 128
# Хеш-пустышка: вход с несуществующим ником занимает столько же времени, сколько с настоящим
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class Credentials(BaseModel):
    nickname: str
    password: str


EXTRA_VIZ_SHOWN = 3


class ProgressIn(BaseModel):
    done: bool


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_password_rules(password: str) -> None:
    if len(password) < PASSWORD_MIN:
        raise HTTPException(400, f"Пароль должен быть не короче {PASSWORD_MIN} символов.")
    if len(password) > PASSWORD_MAX:
        raise HTTPException(400, "Слишком длинный пароль.")


def _set_session(response: Response, user: User) -> None:
    response.set_cookie(
        USER_COOKIE, make_user_token(user.id, user.session_version), max_age=USER_SESSION_DAYS * 86400,
        httponly=True, samesite="lax", secure=config.COOKIE_SECURE, path="/",
    )


@router.get("/auth/me")
def me(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    user = current_user(request, db)
    if user and not is_admin(request):
        touch(db, user, request)
    # admin: в этом браузере открыта админка — тогда сайт показывает всё, и об этом надо предупредить
    return {"user": {"nickname": user.nickname} if user else None, "admin": is_admin(request)}


@router.post("/auth/register", status_code=201)
def register(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_same_origin(request)
    ip = _ip(request)
    register_limit.check(ip)
    nick = body.nickname.strip()
    if not NICK_RE.match(nick):
        raise HTTPException(400, "Ник: от 3 до 32 символов — буквы, цифры, точка, дефис или подчёркивание, без пробелов.")
    check_password_rules(body.password)
    key = nick.lower()
    if db.scalar(select(User.id).where(User.nickname_key == key)):
        raise HTTPException(409, "Такой ник уже занят. Выберите другой.")
    user = User(nickname=nick, nickname_key=key, password_hash=hash_password(body.password),
                session_version=1, last_login_at=datetime.now(timezone.utc))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Такой ник уже занят. Выберите другой.")
    register_limit.hit(ip)
    touch(db, user, request)
    _set_session(response, user)
    return {"user": {"nickname": user.nickname}}


@router.post("/auth/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_same_origin(request)
    ip = _ip(request)
    user_login_limit.check(ip)
    user = db.scalar(select(User).where(User.nickname_key == body.nickname.strip().lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        user_login_limit.hit(ip)
        raise HTTPException(401, "Неверный ник или пароль.")
    user_login_limit.clear(ip)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    touch(db, user, request)
    _set_session(response, user)
    return {"user": {"nickname": user.nickname}}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    check_same_origin(request)
    response.delete_cookie(USER_COOKIE, path="/")
    return {"ok": True}


@router.get("/me/materials")
def my_materials(request: Request, response: Response, db: Session = Depends(get_db)):
    """Папки занятий, открытые ученику (с записью, конспектом, ДЗ и визуализациями), и отдельные визуализации."""
    response.headers["Cache-Control"] = "no-store"
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    lesson_ids = granted_ids(db, user.id, "lesson")
    lessons = db.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids)).order_by(Lesson.number.desc())).all() if lesson_ids else []

    # визуализации по занятиям (только опубликованные), в порядке, заданном админом
    by_lesson: Dict[int, List[int]] = {}
    if lesson_ids:
        for lv in db.scalars(select(LessonViz).where(LessonViz.lesson_id.in_(lesson_ids)).order_by(LessonViz.position, LessonViz.id)):
            by_lesson.setdefault(lv.lesson_id, []).append(lv.viz_id)
    extra_ids = granted_ids(db, user.id, "viz")
    all_viz = {vid for ids in by_lesson.values() for vid in ids} | extra_ids
    viz = {v.id: v for v in db.scalars(
        select(Visualization).options(joinedload(Visualization.section))
        .where(Visualization.id.in_(all_viz), Visualization.is_published.is_(True))
    )} if all_viz else {}
    done = set(db.scalars(select(LessonProgress.lesson_id).where(
        LessonProgress.user_id == user.id, LessonProgress.done.is_(True))))

    in_lessons = {vid for ids in by_lesson.values() for vid in ids}
    # отдельные визуализации: в кабинете только 3 последних открытых, остальные ученик найдёт в хранилище (там они без замка)
    granted_at = {g.item_id: g.created_at for g in db.scalars(select(Grant).where(Grant.user_id == user.id, Grant.kind == "viz"))}
    extra_all = sorted((i for i in extra_ids - in_lessons if i in viz), key=lambda i: (granted_at.get(i), i), reverse=True)
    extra = [viz[i] for i in extra_all[:EXTRA_VIZ_SHOWN]]
    out_lessons = []
    for l in lessons:
        # запись открывается через /watch/<номер>: так виден факт просмотра, а ссылка не лежит в кабинете в открытую
        item = {"pk": l.id, "number": l.number, "title": l.title, "url": f"/watch/{l.number}" if l.url else None, "done": l.id in done}
        item.update(lesson_files(l))
        item["viz"] = [viz_public(viz[i]) for i in by_lesson.get(l.id, []) if i in viz]
        out_lessons.append(item)
    mock_ids = granted_ids(db, user.id, "mock")
    mocks = db.scalars(select(Mock).where(Mock.id.in_(mock_ids)).order_by(Mock.number.desc())).all() if mock_ids else []
    solved = set(db.scalars(select(MockProgress.mock_id).where(MockProgress.user_id == user.id, MockProgress.done.is_(True))))
    out_mocks = []
    for m in mocks:
        item = mock_out(m)
        item["done"] = m.id in solved
        out_mocks.append(item)
    reports = db.scalars(select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc(), Report.id.desc())).all()
    return {
        "user": {"nickname": user.nickname},
        "lessons": out_lessons,
        "viz": [viz_public(v) for v in extra],
        "viz_total": len(extra_all),
        "mocks": out_mocks,
        "reports": [report_out(r) for r in reports],
    }


@router.put("/me/progress/{lesson_pk}")
def set_progress(lesson_pk: int, body: ProgressIn, request: Request, db: Session = Depends(get_db)):
    """Ученик отмечает занятие просмотренным (зелёная папка) или снимает отметку (красная)."""
    check_same_origin(request)
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    if lesson_pk not in granted_ids(db, user.id, "lesson"):
        raise HTTPException(404, "Занятие не найдено.")
    row = db.scalar(select(LessonProgress).where(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_pk))
    if row is None:
        row = LessonProgress(user_id=user.id, lesson_id=lesson_pk)
        db.add(row)
    row.done = body.done
    db.commit()
    return {"done": row.done}


@router.put("/me/mock-progress/{mock_pk}")
def set_mock_progress(mock_pk: int, body: ProgressIn, request: Request, db: Session = Depends(get_db)):
    """Ученик отмечает пробник решённым (зелёный) или снимает отметку (красный)."""
    check_same_origin(request)
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    if mock_pk not in granted_ids(db, user.id, "mock"):
        raise HTTPException(404, "Пробник не найден.")
    row = db.scalar(select(MockProgress).where(MockProgress.user_id == user.id, MockProgress.mock_id == mock_pk))
    if row is None:
        row = MockProgress(user_id=user.id, mock_id=mock_pk)
        db.add(row)
    row.done = body.done
    db.commit()
    return {"done": row.done}


@router.post("/me/ping")
def ping(request: Request, db: Session = Depends(get_db)):
    """Кабинет открыт и виден на экране — продлеваем сеанс (раз в минуту), чтобы длительность была честнее."""
    check_same_origin(request)
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    if not is_admin(request):
        touch(db, user, request)
    return {"ok": True}
