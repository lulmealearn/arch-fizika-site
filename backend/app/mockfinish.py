"""Сдача пробника (решение владельца): бланк первой части уходит на проверку досрочно — кнопкой «Отправить пробник» —
или сам, когда вышло время экзамена (3 ч 55 мин после «Начать»), и никак иначе.

Ответы бланка сохраняются на сервере по ходу (MockProgress.draft), поэтому по окончании времени они уходят, даже если
ученик закрыл страницу. Если фото решений к этому моменту не прикреплены — вторая часть 0 баллов, проверять нечего.
Проверка окончания ленивая, как у сроков ДЗ: при каждом чтении кабинета, админки и страницы проверки."""
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from . import deadlines, files, scale
from .mockcheck import grade
from .models import Mock, MockAttempt, MockProgress, Submission, User
from .tracking import _aware

log = logging.getLogger("mocks")
GRACE = timedelta(minutes=2)  # запас на отправку, начатую в последние секунды (сеть, сборка PDF из фото)
AUTO = "Автоматически"
NO_FILES = "Решения второй части не прикреплены — 0 баллов."


def clean_answers(m: Mock, raw: Optional[dict]) -> Dict[str, str]:
    allowed = {str(t["n"]) for t in (m.answer_key or [])}
    return {str(k): (str(v) if v is not None else "").strip()[:60] for k, v in (raw or {}).items() if str(k) in allowed}


def time_over(row: MockProgress, now: Optional[datetime] = None) -> bool:
    """Время вышло, и запас на отправку тоже."""
    now = now or datetime.now(timezone.utc)
    return row.due_at is not None and row.submitted_at is None and _aware(row.due_at) + GRACE < now


def submit(db, user_id: int, m: Mock, row: MockProgress, answers: Optional[dict],
           parts: List[Tuple[bytes, str, str]], when: Optional[datetime] = None) -> Tuple[Submission, Optional[MockAttempt]]:
    """Сдать пробник: бланк (если есть ключ — проверка сразу) и файлы решений. Без файлов вторая часть сразу 0."""
    attempt = None
    if m.answer_key and not db.scalar(select(MockAttempt.id).where(MockAttempt.user_id == user_id, MockAttempt.mock_id == m.id)):
        given = clean_answers(m, answers if answers is not None else row.draft)
        score, total, details = grade(m.answer_key, given)
        attempt = MockAttempt(user_id=user_id, mock_id=m.id, answers=given, score=score, max_score=total, details=details)
        db.add(attempt)
    s = Submission(user_id=user_id, mock_id=m.id, files=[], overdue=row.overdue_count or 0)
    if not parts:
        sc = scale.get(db)
        s.status, s.checked_by, s.checked_at = "checked", AUTO, datetime.now(timezone.utc)
        s.task_scores = {str(t["n"]): 0 for t in sc["part2"]}
        s.score, s.max_score, s.comment = 0, sc["part2_max"], NO_FILES
    db.add(s)
    db.flush()
    meta = []
    try:
        if parts:
            d = files.submission_dir(s.id)
            d.mkdir(parents=True, exist_ok=True)
            for i, (data, ext, orig) in enumerate(parts, 1):
                name = f"{i:02d}.{ext}"
                (d / name).write_bytes(data)
                meta.append({"name": name, "orig": orig, "type": files.SUB_TYPES[ext], "size": len(data)})
        s.files = meta
        deadlines.submit(row, when)
        row.draft = None
        db.commit()
    except Exception:
        db.rollback()
        files.delete_submission_files(s.id)
        raise
    return s, attempt


def after_submit(sub_id: int) -> None:
    """Что делаем после сдачи: работа с фото — кураторам; без фото (вторая часть 0) — результат сразу ученику.
    И в Google-таблицу."""
    from . import sheets
    from .db import SessionLocal
    from .routes_check import notify_curators, notify_student
    with SessionLocal() as db:
        s = db.get(Submission, sub_id)
        if s is None:
            return
        with_files = bool(s.files)
    try:
        if with_files:
            notify_curators(sub_id)
        else:
            notify_student(sub_id)
        sheets.push_submission(sub_id)
    except Exception:  # noqa: BLE001 — уведомление не должно ломать сдачу
        log.exception("После сдачи пробника %s", sub_id)


def finalize_expired(db, user_id: Optional[int] = None) -> List[int]:
    """Время пробника вышло, а ученик не отправил — бланк уходит сам (с ответами, что успел вписать). Возвращает id сдач."""
    q = select(MockProgress).where(MockProgress.due_at.is_not(None), MockProgress.submitted_at.is_(None))
    if user_id is not None:
        q = q.where(MockProgress.user_id == user_id)
    done: List[int] = []
    now = datetime.now(timezone.utc)
    for row in db.scalars(q).all():
        if not time_over(row, now):
            continue
        m = db.get(Mock, row.mock_id)
        u = db.get(User, row.user_id)
        if m is None or u is None or u.role == "curator":
            continue
        try:
            s, _ = submit(db, u.id, m, row, None, [], when=_aware(row.due_at))
            done.append(s.id)
        except Exception:  # noqa: BLE001
            log.exception("Пробник %s ученика %s не отправился сам", m.number, u.id)
    for sid in done:
        threading.Thread(target=after_submit, args=(sid,), daemon=True).start()
    return done
