"""Кто что может открыть: текущий ученик, его ручные доступы и проверка перед выдачей материала.

Ученику открыто занятие (grants.kind = lesson) — он видит папку, но её содержимое (запись, конспект, ДЗ, визуализации)
открывается только после того, как он нажал «Начать» (срок на ДЗ, deadlines.py) — иначе ДЗ можно было бы читать до старта срока.
Отдельную закрытую визуализацию можно открыть и без занятия (grants.kind = viz)."""
from typing import Dict, Iterable, List, Optional, Set

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import GRANT_KINDS, Grant, LessonProgress, LessonViz, MockProgress, User
from .security import is_admin, read_user_token


def current_user(request: Request, db: Session) -> Optional[User]:
    """Ученик из cookie. Сброшенный пароль (новая версия сессии) или удалённый аккаунт — значит, не вошёл."""
    data = read_user_token(request)
    if not data:
        return None
    user = db.get(User, data["u"])
    if not user or user.session_version != data.get("v"):
        return None
    return user


def granted_ids(db: Session, user_id: int, kind: str) -> Set[int]:
    return set(db.scalars(select(Grant.item_id).where(Grant.user_id == user_id, Grant.kind == kind)))


def started_lesson_ids(db: Session, user_id: int) -> Set[int]:
    """Открытые ученику занятия, где он хоть раз нажал «Начать», — их материалы доступны (и после просрочки тоже)."""
    granted = granted_ids(db, user_id, "lesson")
    if not granted:
        return set()
    return set(db.scalars(select(LessonProgress.lesson_id).where(
        LessonProgress.user_id == user_id, LessonProgress.first_started_at.is_not(None), LessonProgress.lesson_id.in_(granted))))


def opened_viz_ids(db: Session, user_id: int) -> Set[int]:
    """Визуализации, открытые ученику: отдельно или через начатые им занятия."""
    lessons = started_lesson_ids(db, user_id)
    via_lessons = set(db.scalars(select(LessonViz.viz_id).where(LessonViz.lesson_id.in_(lessons)))) if lessons else set()
    return granted_ids(db, user_id, "viz") | via_lessons


def can_open(db: Session, request: Request, kind: str, item_id: int, user: Optional[User] = None) -> bool:
    """Закрытый материал: админ видит всё, ученик — только то, что ему открыли."""
    if is_admin(request):
        return True
    user = user or current_user(request, db)
    if not user:
        return False
    if kind == "viz":
        return item_id in opened_viz_ids(db, user.id)
    return db.scalar(select(Grant.id).where(
        Grant.user_id == user.id, Grant.kind == kind, Grant.item_id == item_id)) is not None


def lesson_unlocked(db: Session, request: Request, lesson_id: int, user: Optional[User]) -> bool:
    """Материалы занятия: админ — всегда, ученик — если занятие открыто ему и он нажал «Начать»."""
    if is_admin(request):
        return True
    return user is not None and lesson_id in started_lesson_ids(db, user.id)


def mock_unlocked(db: Session, request: Request, mock_id: int, user: Optional[User]) -> bool:
    """Вариант пробника: админ — всегда, ученик — после «Начать» (иначе вариант решают до старта срока)."""
    if is_admin(request):
        return True
    return user is not None and db.scalar(select(MockProgress.id).where(
        MockProgress.user_id == user.id, MockProgress.mock_id == mock_id, MockProgress.first_started_at.is_not(None))) is not None


def user_grants(db: Session) -> Dict[int, Dict[str, List[int]]]:
    """Все доступы одним запросом: {user_id: {"viz": [...], "lesson": [...]}}."""
    out: Dict[int, Dict[str, List[int]]] = {}
    for g in db.scalars(select(Grant).where(Grant.kind.in_(GRANT_KINDS))):
        out.setdefault(g.user_id, {k: [] for k in GRANT_KINDS})[g.kind].append(g.item_id)
    return out


def item_users(db: Session, kind: str) -> Dict[int, List[int]]:
    """Кому открыт каждый материал данного вида: {item_id: [user_id, ...]}."""
    out: Dict[int, List[int]] = {}
    for g in db.scalars(select(Grant).where(Grant.kind == kind)):
        out.setdefault(g.item_id, []).append(g.user_id)
    return out


def set_user_grants(db: Session, user_id: int, kind: str, item_ids: Iterable[int]) -> None:
    """Заменить набор материалов вида kind, открытых ученику."""
    want = set(item_ids)
    have = granted_ids(db, user_id, kind)
    if have - want:
        db.execute(delete(Grant).where(Grant.user_id == user_id, Grant.kind == kind, Grant.item_id.in_(have - want)))
    for item_id in want - have:
        db.add(Grant(user_id=user_id, kind=kind, item_id=item_id))


def set_item_users(db: Session, kind: str, item_id: int, user_ids: Iterable[int]) -> None:
    """Заменить список учеников, которым открыт один материал."""
    want = set(user_ids)
    have = set(db.scalars(select(Grant.user_id).where(Grant.kind == kind, Grant.item_id == item_id)))
    if have - want:
        db.execute(delete(Grant).where(Grant.kind == kind, Grant.item_id == item_id, Grant.user_id.in_(have - want)))
    for uid in want - have:
        db.add(Grant(user_id=uid, kind=kind, item_id=item_id))


def drop_item(db: Session, kind: str, item_id: int) -> None:
    """Материал удалён — убрать и все доступы к нему."""
    db.execute(delete(Grant).where(Grant.kind == kind, Grant.item_id == item_id))
