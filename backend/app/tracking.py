"""Учёт активности учеников: сеансы (заходы на сайт) и открытые материалы. Только для админки."""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import User, View, Visit

SESSION_GAP = timedelta(minutes=30)   # перерыв дольше — значит, новый сеанс
VIEW_DEDUP = timedelta(minutes=10)    # одно и то же открытие подряд не дублируем
KEEP = timedelta(days=365)            # старше года — удаляем при запуске


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite отдаёт время без часового пояса — считаем его UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def device_label(ua: str) -> str:
    """Коротко: «Телефон Android · Chrome», «Компьютер Windows · Яндекс Браузер»."""
    ua = ua or ""
    if re.search(r"iPhone", ua):
        os_ = "iPhone"
    elif re.search(r"iPad", ua):
        os_ = "iPad"
    elif re.search(r"Android", ua):
        os_ = "Android" + (" (планшет)" if "Mobile" not in ua else "")
    elif "Windows" in ua:
        os_ = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_ = "Mac"
    elif "Linux" in ua:
        os_ = "Linux"
    else:
        os_ = "неизвестное устройство"
    if "Telegram" in ua:
        br = "Telegram"
    elif "YaBrowser" in ua or "YaSearchBrowser" in ua:
        br = "Яндекс Браузер"
    elif "Edg/" in ua:
        br = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        br = "Opera"
    elif "Firefox/" in ua or "FxiOS" in ua:
        br = "Firefox"
    elif "CriOS" in ua or ("Chrome/" in ua and "Chromium" not in ua):
        br = "Chrome"
    elif "Safari/" in ua:
        br = "Safari"
    else:
        br = "браузер"
    return f"{os_} · {br}"[:80]


def touch(db: Session, user: Optional[User], request: Request) -> None:
    """Отметить активность: продлить текущий сеанс или начать новый."""
    if user is None:
        return
    now = _now()
    device = device_label(request.headers.get("user-agent", ""))
    v = db.scalar(select(Visit).where(Visit.user_id == user.id).order_by(Visit.last_seen_at.desc(), Visit.id.desc()).limit(1))
    if v is not None and v.device == device and now - _aware(v.last_seen_at) <= SESSION_GAP:
        v.last_seen_at = now
        v.hits = (v.hits or 0) + 1
    else:
        db.add(Visit(user_id=user.id, started_at=now, last_seen_at=now, device=device, hits=1))
    db.commit()


def record_view(db: Session, user: Optional[User], request: Request, kind: str, ref: str, title: str) -> None:
    """Ученик открыл материал (kind: video, notes, hw, viz, mock, report)."""
    if user is None:
        return
    now = _now()
    last = db.scalar(select(View).where(View.user_id == user.id).order_by(View.at.desc(), View.id.desc()).limit(1))
    if not (last is not None and last.kind == kind and last.ref == ref and now - _aware(last.at) <= VIEW_DEDUP):
        db.add(View(user_id=user.id, kind=kind, ref=str(ref)[:120], title=(title or "")[:200], at=now))
    touch(db, user, request)  # заодно продлевает сеанс и сохраняет


def prune(db: Session) -> None:
    edge = _now() - KEEP
    db.execute(delete(Visit).where(Visit.last_seen_at < edge))
    db.execute(delete(View).where(View.at < edge))
    db.commit()
