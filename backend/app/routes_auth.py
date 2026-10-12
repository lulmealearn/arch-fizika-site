"""Ученики: регистрация, вход, выход и «мои материалы» для личного кабинета."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import config
from .access import current_user, granted_ids
from .db import get_db
from .models import Homework, Lesson, User, Visualization
from .security import (USER_COOKIE, USER_SESSION_DAYS, check_same_origin, hash_password, make_user_token,
                       register_limit, user_login_limit, verify_password)
from .serialize import hw_out, lesson_out, viz_public

router = APIRouter(prefix="/api")

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.\-]{3,32}$")
PASSWORD_MIN, PASSWORD_MAX = 6, 128
# Хеш-пустышка: вход с несуществующим ником занимает столько же времени, сколько с настоящим
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class Credentials(BaseModel):
    nickname: str
    password: str


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
    return {"user": {"nickname": user.nickname} if user else None}


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
    _set_session(response, user)
    return {"user": {"nickname": user.nickname}}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    check_same_origin(request)
    response.delete_cookie(USER_COOKIE, path="/")
    return {"ok": True}


@router.get("/me/materials")
def my_materials(request: Request, response: Response, db: Session = Depends(get_db)):
    """Всё, что админ открыл этому ученику: закрытые визуализации, домашки и уроки."""
    response.headers["Cache-Control"] = "no-store"
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "Войдите в личный кабинет.")
    viz_ids, hw_ids, lesson_ids = (granted_ids(db, user.id, k) for k in ("viz", "hw", "lesson"))
    viz = db.scalars(
        select(Visualization).options(joinedload(Visualization.section))
        .where(Visualization.id.in_(viz_ids or [-1]), Visualization.is_published.is_(True), Visualization.access == "private")
        .order_by(Visualization.position, Visualization.id)
    ).all() if viz_ids else []
    hws = db.scalars(select(Homework).where(Homework.id.in_(hw_ids)).order_by(Homework.number.desc())).all() if hw_ids else []
    lessons = db.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids)).order_by(Lesson.number.desc())).all() if lesson_ids else []
    return {
        "user": {"nickname": user.nickname},
        "viz": [viz_public(v) for v in viz],
        "homeworks": [hw_out(h) for h in hws],
        "lessons": [lesson_out(l) for l in lessons],
    }
