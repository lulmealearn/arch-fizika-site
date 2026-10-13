"""Срок на домашнее задание занятия и на пробник (одна логика, разные сроки по умолчанию: 3 дня и неделя).

Состояния (решение владельца):
  «Не начато» → ученик нажимает «Начать» и подтверждает → «В работе», идёт срок (по умолчанию 3 дня, у занятия можно
  задать другой) → ученик нажимает «Сдал» → «Сдано».
  Если срок истёк, а «Сдал» не нажато, занятие само возвращается в «Не начато»: просрочка остаётся в счётчике
  (overdue_count), а новый срок ученик берёт той же кнопкой «Начать».
Время истечения проверяется при каждом чтении (settle) — фоновых задач нет.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import DEFAULT_DEADLINE_DAYS, DEFAULT_MOCK_DEADLINE_DAYS, Mock
from .serialize import _iso
from .tracking import _aware

DEFAULT_DAYS = DEFAULT_DEADLINE_DAYS
MAX_DAYS = 60


def default_days(item) -> int:
    return DEFAULT_MOCK_DEADLINE_DAYS if isinstance(item, Mock) else DEFAULT_DAYS


def days_for(item) -> int:
    """Срок занятия или пробника: свой (deadline_days) или по умолчанию — 3 дня у занятия, неделя у пробника."""
    return item.deadline_days or default_days(item)


def settle(p, now: Optional[datetime] = None) -> bool:
    """Срок истёк без сдачи → вернуть в «Не начато» и засчитать просрочку. True, если что-то поменялось."""
    if p is None or p.submitted_at is not None or p.due_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if _aware(p.due_at) > now:
        return False
    p.overdue_count = (p.overdue_count or 0) + 1
    p.last_overdue_at = p.due_at
    p.started_at = None
    p.due_at = None
    p.done = False
    return True


def state(p) -> str:
    if p is None:
        return "todo"
    if p.submitted_at is not None:
        return "done"
    if p.due_at is not None:
        return "active"
    return "todo"


def status_out(p, lesson) -> Dict[str, Any]:
    """Состояние для кабинета и админки (после settle)."""
    st = state(p)
    out = {"state": st, "days": days_for(lesson), "overdue": (p.overdue_count or 0) if p else 0,
           "started_at": None, "due_at": None, "submitted_at": None, "first_started_at": None, "last_overdue_at": None}
    if p is not None:
        out.update(started_at=_iso(p.started_at), due_at=_iso(p.due_at), submitted_at=_iso(p.submitted_at),
                   first_started_at=_iso(p.first_started_at), last_overdue_at=_iso(p.last_overdue_at))
    return out


def start(p, lesson, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    p.started_at = now
    p.due_at = now + timedelta(days=days_for(lesson))
    if p.first_started_at is None:
        p.first_started_at = now


def submit(p, now: Optional[datetime] = None) -> None:
    p.submitted_at = now or datetime.now(timezone.utc)
    p.done = True


def user_deadlines(db, user_id: int) -> List[Dict[str, Any]]:
    """Сроки ученика для кнопки «Дедлайны» и для админки: что в работе (сколько осталось) и что просрочено
    (срок истёк, ждёт нового «Начать»). Сначала в работе — ближайшие сверху."""
    from sqlalchemy import select
    from .access import granted_ids
    from .models import Lesson, LessonProgress, MockProgress
    out: List[Dict[str, Any]] = []
    for model, prog, col, kind, label, href in ((Lesson, LessonProgress, "lesson_id", "lesson", "Занятие", "z"),
                                                (Mock, MockProgress, "mock_id", "mock", "Пробник", "p")):
        ids = granted_ids(db, user_id, kind)
        if not ids:
            continue
        rows = db.scalars(select(prog).where(prog.user_id == user_id, getattr(prog, col).in_(ids))).all()
        if any([settle(p) for p in rows]):
            db.commit()
        items = {i.id: i for i in db.scalars(select(model).where(model.id.in_({getattr(p, col) for p in rows})))} if rows else {}
        for p in rows:
            st = state(p)
            it = items.get(getattr(p, col))
            if it is None or not (st == "active" or (st == "todo" and p.overdue_count)):
                continue
            d = status_out(p, it)
            out.append({"kind": kind, "label": f"{label} № {it.number}", "title": it.title or "", "url": f"/account/#{href}{it.number}",
                        "state": st, "started_at": d["started_at"], "due_at": d["due_at"], "days": d["days"],
                        "overdue": d["overdue"], "last_overdue_at": d["last_overdue_at"]})
    out.sort(key=lambda x: (x["state"] != "active", x["due_at"] or "", x["label"]))
    return out
