"""Связь с Google-таблицей «Ученики — учёт занятий» (решение владельца: таблица — главное хранилище результатов).

Сайт не ходит в Google API напрямую: в таблице работает отдельное веб-приложение Apps Script (tools/sheets/site.gs),
сайт шлёт ему POST с JSON и общим секретом. Так не нужны ни Google Cloud, ни ключи сервисного аккаунта.

Ученик находится по chat_id в первой строке его вкладки (или по вкладке, указанной в админке).
ДЗ пишется в строку с той же темой урока, пробник № N — в столбец N вкладки «П-…» (решения владельца)."""
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from . import config
from .db import SessionLocal
from .models import Lesson, Mock, MockAttempt, Submission, User

log = logging.getLogger("sheets")
TIMEOUT = 40  # Apps Script отвечает за 1–5 секунд, при холодном старте дольше


class SheetsError(Exception):
    pass


def enabled() -> bool:
    return bool(config.SHEETS_URL and config.SHEETS_SECRET)


def call(action: str, **payload) -> dict:
    """POST в веб-приложение. Apps Script отвечает редиректом 302 на googleusercontent.com — urllib идёт по нему GET-ом,
    так и задумано у Google."""
    if not enabled():
        raise SheetsError("Таблица не подключена (python run.py set-sheet).")
    body = json.dumps(dict(payload, action=action, secret=config.SHEETS_SECRET), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(config.SHEETS_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SheetsError("Google не пустил к скрипту: при развёртывании выберите «У кого есть доступ: все» "
                              "и «Запуск от имени: я».")
        if e.code == 404:
            raise SheetsError("Скрипт не найден по адресу из .env — проверьте SHEETS_URL (он заканчивается на /exec).")
        raise SheetsError(f"Таблица ответила ошибкой HTTP {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SheetsError(f"Нет связи с таблицей: {getattr(e, 'reason', e)}")
    try:
        data = json.loads(raw)
    except ValueError:
        if "<html" in raw[:500].lower():
            raise SheetsError("Вместо ответа скрипта пришла страница Google — скорее всего, нужен доступ «все» "
                              "при развёртывании или скрипт ещё не разрешил доступ к таблице (запустите testAccess).")
        raise SheetsError("Скрипт ответил не JSON.")
    if not data.get("ok"):
        raise SheetsError(data.get("error") or "Скрипт вернул ошибку без описания.")
    return data


def who(u: User) -> dict:
    """Как скрипт найдёт вкладку ученика."""
    if u.sheet_tab:
        return {"tab": u.sheet_tab}
    return {"chat_id": u.tg_chat_id or ""}


def linked(u: User) -> bool:
    return bool(u.sheet_tab or u.tg_chat_id)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def payload_for(db, s: Submission) -> Optional[tuple]:
    """(действие, данные) для записи сдачи в таблицу; None — писать нечего."""
    u = db.get(User, s.user_id)
    if s.lesson_id:
        l = db.get(Lesson, s.lesson_id)
        data = dict(who(u), topic=l.title or "", row=s.sheet_row, submitted_at=_iso(s.created_at))
        if s.status == "checked":  # до проверки в таблицу уходят только «ДЗ сдал» и дата сдачи
            data.update(correct=s.score, total=s.max_score, comment=s.comment or "")
        return "hw", data
    if s.mock_id:
        m = db.get(Mock, s.mock_id)
        a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == s.user_id, MockAttempt.mock_id == s.mock_id))
        scores = {}
        if a:
            for d in a.details or []:
                scores[str(d["n"])] = d["points"]
        if s.status == "checked":
            scores.update({str(k): v for k, v in (s.task_scores or {}).items()})
        if not scores:
            return None
        return "mock", dict(who(u), number=m.number, date=_iso(s.created_at), scores=scores)
    return None


def push_submission(sub_id: int) -> None:
    """Фоном: записать сдачу в таблицу. Ошибка не мешает ни ученику, ни куратору — видна на странице проверки."""
    if not enabled():
        return
    with SessionLocal() as db:
        s = db.get(Submission, sub_id)
        if s is None:
            return
        u = db.get(User, s.user_id)
        if u is None or not linked(u):
            s.sheet_error = "У ученика не указан ни Telegram chat id, ни вкладка в таблице (админка → «Ученики» → «Telegram»)."
            db.commit()
            return
        job = payload_for(db, s)
        if job is None:
            return
        action, data = job
        try:
            res = call(action, **data)
            s.sheet_synced_at = datetime.now(timezone.utc)
            s.sheet_error = ""
            if action == "hw":
                s.sheet_row = res.get("row")
                s.sheet_place = f"«{res.get('tab')}», ДЗ № {res.get('hw') or '?'} (строка {res.get('row')})"
            else:
                s.sheet_place = f"«{res.get('tab')}», пробник № {data['number']}"
        except SheetsError as e:
            s.sheet_error = str(e)[:400]
            log.warning("Сдача %s не записана в таблицу: %s", s.id, e)
        db.commit()
