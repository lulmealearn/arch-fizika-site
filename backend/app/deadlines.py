"""Срок на домашнее задание занятия и на пробник (одна логика, разные сроки по умолчанию: 3 дня и неделя).

Состояния (решение владельца):
  «Не начато» → ученик нажимает «Начать» и подтверждает → «В работе», идёт срок (по умолчанию 3 дня, у занятия можно
  задать другой) → ученик нажимает «Сдал» → «Сдано».
  Если срок истёк, а «Сдал» не нажато, занятие само возвращается в «Не начато»: просрочка остаётся в счётчике
  (overdue_count), а новый срок ученик берёт той же кнопкой «Начать».
Время истечения проверяется при каждом чтении (settle) — фоновых задач нет.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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
