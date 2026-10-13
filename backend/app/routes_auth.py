"""Ученики: регистрация, вход, выход и «мои материалы» для личного кабинета."""
import re
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import config, deadlines
from .access import current_user, granted_ids
from .tracking import touch
from .db import get_db
from .mockcheck import grade
from .models import Grant, Lesson, Section, LessonProgress, LessonViz, Mock, MockAttempt, MockProgress, Report, User, Visualization
from .security import (USER_COOKIE, USER_SESSION_DAYS, check_same_origin, hash_password, is_admin, make_user_token,
                       register_limit, user_login_limit, verify_password)
from .serialize import _iso, lesson_files, section_out, mock_out, report_out, viz_public

router = APIRouter(prefix="/api")

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.\-]{3,32}$")
PASSWORD_MIN, PASSWORD_MAX = 6, 128
# Хеш-пустышка: вход с несуществующим ником занимает столько же времени, сколько с настоящим
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class Credentials(BaseModel):
    nickname: str
    password: str


EXTRA_VIZ_SHOWN = 3


class AnswersIn(BaseModel):
    answers: Dict[str, str]


def attempt_out(a) -> dict:
    """Результат первой части для ученика: баллы и разбор с правильными ответами (решение владельца — показывать все)."""
    return {"score": a.score, "max": a.max_score, "submitted_at": _iso(a.submitted_at),
            "details": a.details or []}


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
    progress = {p.lesson_id: p for p in db.scalars(select(LessonProgress).where(LessonProgress.user_id == user.id))}
    if any([deadlines.settle(p) for p in progress.values()]):
        db.commit()  # истёкшие сроки вернулись в «Не начато»

    in_lessons = {vid for ids in by_lesson.values() for vid in ids}
    # отдельные визуализации: в кабинете только 3 последних открытых, остальные ученик найдёт в хранилище (там они без замка)
    granted_at = {g.item_id: g.created_at for g in db.scalars(select(Grant).where(Grant.user_id == user.id, Grant.kind == "viz"))}
    extra_all = sorted((i for i in extra_ids - in_lessons if i in viz), key=lambda i: (granted_at.get(i), i), reverse=True)
    extra = [viz[i] for i in extra_all[:EXTRA_VIZ_SHOWN]]
    out_lessons = []
    for l in lessons:
        # запись открывается через /watch/<номер>: так виден факт просмотра, а ссылка не лежит в кабинете в открытую
        item = {"pk": l.id, "number": l.number, "title": l.title, "url": f"/watch/{l.number}" if l.url else None,
                "section": l.section.slug if l.section else None}
        item["deadline"] = deadlines.status_out(progress.get(l.id), l)
        item["done"] = item["deadline"]["state"] == "done"
        item.update(lesson_files(l))
        item["viz"] = [viz_public(viz[i]) for i in by_lesson.get(l.id, []) if i in viz]
        # что лежит в папке — показываем всегда, а сами материалы — только после «Начать» (иначе ДЗ читают до старта срока)
        item["inside"] = {"video": bool(l.url), "notes": bool(item.get("notes_url")), "hw": bool(item.get("hw_url")), "viz": len(item["viz"])}
        p = progress.get(l.id)
        item["locked"] = not (p and p.first_started_at)
        if item["locked"]:
            item.update(url=None, notes_url=None, hw_url=None, viz=[])
        out_lessons.append(item)
    mock_ids = granted_ids(db, user.id, "mock")
    mocks = db.scalars(select(Mock).where(Mock.id.in_(mock_ids)).order_by(Mock.number.desc())).all() if mock_ids else []
    mprog = {p.mock_id: p for p in db.scalars(select(MockProgress).where(MockProgress.user_id == user.id))}
    if any([deadlines.settle(p) for p in mprog.values()]):
        db.commit()
    tries = {a.mock_id: a for a in db.scalars(select(MockAttempt).where(MockAttempt.user_id == user.id))}
    out_mocks = []
    for m in mocks:
        item = mock_out(m)
        p = mprog.get(m.id)
        item["deadline"] = deadlines.status_out(p, m)
        item["done"] = item["deadline"]["state"] == "done"
        item["result"] = attempt_out(tries[m.id]) if m.id in tries else None
        # как у занятий: вариант открывается только после «Начать» — иначе его решают до старта срока
        item["locked"] = not (p and p.first_started_at)
        if item["locked"]:
            item["url"] = None
        out_mocks.append(item)
    reports = db.scalars(select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc(), Report.id.desc())).all()
    return {
        "user": {"nickname": user.nickname},
        "lessons": out_lessons,
        "sections": [section_out(s) for s in db.scalars(select(Section).order_by(Section.position))],
        "viz": [viz_public(v) for v in extra],
        "viz_total": len(extra_all),
        "mocks": out_mocks,
        "reports": [report_out(r) for r in reports],
    }


KINDS = {"lessons": (Lesson, LessonProgress, "lesson_id", "lesson", "Занятие не найдено.", "Это занятие уже сдано."),
         "mocks": (Mock, MockProgress, "mock_id", "mock", "Пробник не найден.", "Этот пробник уже сдан.")}


def _my_item(request: Request, db: Session, kind: str, pk: int):
    """Занятие или пробник ученика и строка его срока (истёкший срок сразу засчитывается)."""
    if kind not in KINDS:
        raise HTTPException(404, "Не найдено.")
    model, prog, col, grant_kind, not_found, _ = KINDS[kind]
    check_same_origin(request)
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    item = db.get(model, pk)
    if not item or pk not in granted_ids(db, user.id, grant_kind):
        raise HTTPException(404, not_found)
    row = db.scalar(select(prog).where(prog.user_id == user.id, getattr(prog, col) == pk))
    if row is None:
        row = prog(user_id=user.id, done=False, overdue_count=0, **{col: pk})
        db.add(row)
    deadlines.settle(row)
    return user, item, row


@router.post("/me/{kind}/{pk}/start")
def start_item(kind: str, pk: int, request: Request, db: Session = Depends(get_db)):
    """Ученик подтвердил, что начинает (ДЗ занятия или пробник): материалы открываются, с этой минуты идёт срок.
    Повторное нажатие срок не продлевает."""
    _, item, row = _my_item(request, db, kind, pk)
    st = deadlines.state(row)
    if st == "done":
        raise HTTPException(409, KINDS[kind][5])
    if st == "todo":
        deadlines.start(row, item)
    db.commit()
    return {"deadline": deadlines.status_out(row, item)}


def _need_active(db: Session, row) -> None:
    if deadlines.state(row) == "todo":
        db.commit()  # могла засчитаться просрочка
        msg = "Срок истёк. Нажмите «Начать», чтобы взять новый срок." if row.overdue_count else "Сначала нажмите «Начать»."
        raise HTTPException(409, msg)


@router.post("/me/{kind}/{pk}/submit")
def submit_item(kind: str, pk: int, request: Request, db: Session = Depends(get_db)):
    """Ученик отметил, что сдал. Только пока идёт срок: если он истёк, сначала берут новый.
    Пробник с автопроверкой сдаётся бланком ответов, а не этой кнопкой."""
    _, item, row = _my_item(request, db, kind, pk)
    if kind == "mocks" and item.answer_key and deadlines.state(row) != "done":
        raise HTTPException(400, "Этот пробник сдаётся бланком ответов.")
    _need_active(db, row)
    if deadlines.state(row) == "active":
        deadlines.submit(row)
    db.commit()
    return {"deadline": deadlines.status_out(row, item)}


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


@router.post("/me/mocks/{mock_pk}/answers")
def submit_answers(mock_pk: int, body: AnswersIn, request: Request, db: Session = Depends(get_db)):
    """Бланк ответов первой части: проверка по ключу на сервере. Попытка одна, только пока идёт срок;
    отправка бланка и есть сдача пробника."""
    user, m, row = _my_item(request, db, "mocks", mock_pk)
    if not m.answer_key:
        raise HTTPException(400, "У этого пробника нет автопроверки.")
    if db.scalar(select(MockAttempt.id).where(MockAttempt.user_id == user.id, MockAttempt.mock_id == m.id)):
        raise HTTPException(409, "Ответы на этот пробник уже отправлены.")
    _need_active(db, row)
    allowed = {str(t["n"]) for t in m.answer_key}
    answers = {k: (v or "").strip()[:60] for k, v in body.answers.items() if k in allowed}
    score, total, details = grade(m.answer_key, answers)
    a = MockAttempt(user_id=user.id, mock_id=m.id, answers=answers, score=score, max_score=total, details=details)
    db.add(a)
    deadlines.submit(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ответы на этот пробник уже отправлены.")
    touch(db, user, request)
    out = attempt_out(a)
    out["deadline"] = deadlines.status_out(row, m)
    return out
