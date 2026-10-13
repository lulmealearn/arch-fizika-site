"""Админка: связь с Google-таблицей и отчёты, собранные из неё.

Раз в месяц (с 1-го числа, при первом открытии админки) сайт сам собирает черновики отчётов за прошлый месяц
для всех учеников, у которых в таблице были занятия. Владелец открывает черновик, дописывает комментарий
и публикует — отчёт появляется у ученика во вкладке «Отчёты», бот присылает ему ссылку."""
import logging
import threading
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, report_build, sheets, telegram
from .db import SessionLocal, get_db
from .models import Report, Setting, User
from .security import require_admin
from .serialize import report_out

log = logging.getLogger("reports")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
AUTO_KEY = "reports_auto"
_lock = threading.Lock()


def _report(db: Session, pk: int, auto: bool = True) -> Report:
    r = db.get(Report, pk)
    if not r:
        raise HTTPException(404, "Отчёт не найден.")
    if auto and r.kind != "auto":
        raise HTTPException(400, "Это загруженный PDF — его можно только удалить.")
    return r


def _dates(d_from: str, d_to: str):
    try:
        a, b = date.fromisoformat(d_from), date.fromisoformat(d_to)
    except ValueError:
        raise HTTPException(400, "Даты — в виде ГГГГ-ММ-ДД.")
    if a > b or (b - a).days > 400:
        raise HTTPException(400, "Начало периода должно быть раньше конца, период — не больше года.")
    return a, b


def _collect_into(db: Session, r: Report, u: User) -> None:
    a, b = date.fromisoformat(r.period_from), date.fromisoformat(r.period_to)
    try:
        r.data = report_build.collect(db, u, a, b)
    except sheets.SheetsError as e:
        raise HTTPException(400, f"Таблица: {e}")
    r.collected_at = datetime.now(timezone.utc)


# ── Таблица ──
@router.get("/sheet")
def sheet_status(db: Session = Depends(get_db)):
    """Подключена ли таблица, какие в ней вкладки учеников и кто из учеников сайта к какой привязан."""
    if not sheets.enabled():
        return {"enabled": False}
    try:
        ping = sheets.call("ping")
        tabs = sheets.call("tabs")["tabs"]
    except sheets.SheetsError as e:
        return {"enabled": True, "ok": False, "error": str(e)}
    users = db.scalars(select(User).where(User.role != "curator").order_by(User.nickname_key)).all()
    by_tab = {t["name"]: t for t in tabs}
    out_users = []
    for u in users:
        tab = None
        if u.sheet_tab:
            tab = u.sheet_tab if u.sheet_tab in by_tab else None
        elif u.tg_chat_id:
            hits = [t["name"] for t in tabs if u.tg_chat_id in t["chat_ids"]]
            tab = hits[0] if len(hits) == 1 else None
        out_users.append({"id": u.id, "nickname": u.nickname, "tab": tab, "manual": bool(u.sheet_tab),
                          "chat": bool(u.tg_chat_id)})
    for t in tabs:
        t["users"] = [x["nickname"] for x in out_users if x["tab"] == t["name"]]
    return {"enabled": True, "ok": True, "title": ping.get("title"), "tabs": tabs, "users": out_users}


# ── Отчёты из таблицы ──
class AutoIn(BaseModel):
    period_from: str
    period_to: str


class CommentIn(BaseModel):
    comment: str = ""


@router.post("/users/{pk}/reports/auto", status_code=201)
def reports_auto_create(pk: int, body: AutoIn, db: Session = Depends(get_db)):
    """Собрать черновик отчёта за период из таблицы."""
    u = db.get(User, pk)
    if not u:
        raise HTTPException(404, "Ученик не найден.")
    if not sheets.enabled():
        raise HTTPException(400, "Таблица не подключена (python run.py set-sheet).")
    if not sheets.linked(u):
        raise HTTPException(400, "У ученика не указан ни Telegram chat id, ни вкладка в таблице (кнопка «Telegram»).")
    a, b = _dates(body.period_from, body.period_to)
    r = Report(user_id=u.id, title=report_build.report_title(a, b), file_name="", kind="auto", status="draft",
               period_from=a.isoformat(), period_to=b.isoformat(), comment="")
    _collect_into(db, r, u)
    db.add(r)
    db.commit()
    return report_out(r)


@router.post("/reports/{pk}/refresh")
def reports_refresh(pk: int, db: Session = Depends(get_db)):
    """Заново взять цифры из таблицы (если там что-то поправили). Комментарий остаётся."""
    r = _report(db, pk)
    _collect_into(db, r, db.get(User, r.user_id))
    db.commit()
    return report_out(r)


@router.put("/reports/{pk}")
def reports_comment(pk: int, body: CommentIn, db: Session = Depends(get_db)):
    r = _report(db, pk)
    r.comment = (body.comment or "").strip()[:5000]
    db.commit()
    return report_out(r)


@router.post("/reports/{pk}/publish")
def reports_publish(pk: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Опубликовать: отчёт появляется в кабинете ученика, бот присылает ему ссылку (если есть chat id)."""
    r = _report(db, pk)
    first = r.published_at is None
    r.status = "published"
    r.published_at = r.published_at or datetime.now(timezone.utc)
    db.commit()
    if first:
        background.add_task(notify_report, r.id)
    return report_out(r)


@router.post("/reports/{pk}/unpublish")
def reports_unpublish(pk: int, db: Session = Depends(get_db)):
    r = _report(db, pk)
    r.status = "draft"
    db.commit()
    return report_out(r)


def notify_report(report_id: int) -> None:
    with SessionLocal() as db:
        r = db.get(Report, report_id)
        if r is None:
            return
        u = db.get(User, r.user_id)
        if not telegram.enabled() or not (u and u.tg_chat_id):
            r.notify_error = "Бот не настроен или у ученика нет chat id — отчёт виден только в кабинете."
        else:
            try:
                telegram.send_text(u.tg_chat_id, f"Готов ежемесячный отчёт: {r.title[0].lower() + r.title[1:]}.\n"
                                                 f"Посмотреть: {config.SITE_URL}/report/{r.id}")
                r.notify_error = ""
            except telegram.TelegramError as e:
                r.notify_error = str(e)[:300]
        db.commit()


# ── Черновики раз в месяц ──
def _auto_state(db: Session) -> dict:
    row = db.get(Setting, AUTO_KEY)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def _save_auto(db: Session, value: dict) -> None:
    row = db.get(Setting, AUTO_KEY)
    if row is None:
        db.add(Setting(key=AUTO_KEY, value=value))
    else:
        row.value = value
    db.commit()


def make_monthly(d_from: date, d_to: date) -> None:
    """Черновики за период всем привязанным ученикам, у кого их ещё нет и у кого были занятия."""
    if not _lock.acquire(blocking=False):
        return
    try:
        with SessionLocal() as db:
            made: List[str] = []
            skipped: List[str] = []
            errors: List[str] = []
            for u in db.scalars(select(User).where(User.role != "curator").order_by(User.nickname_key)).all():
                if not sheets.linked(u):
                    continue
                exists = db.scalar(select(Report.id).where(Report.user_id == u.id, Report.kind == "auto",
                                                         Report.period_from == d_from.isoformat(),
                                                         Report.period_to == d_to.isoformat()))
                if exists:
                    continue
                try:
                    data = report_build.collect(db, u, d_from, d_to)
                except sheets.SheetsError as e:
                    errors.append(f"{u.nickname}: {e}")
                    continue
                if not data["lessons"]:
                    skipped.append(u.nickname)
                    continue
                db.add(Report(user_id=u.id, title=report_build.report_title(d_from, d_to), file_name="", kind="auto",
                              status="draft", period_from=d_from.isoformat(), period_to=d_to.isoformat(), comment="",
                              data=data, collected_at=datetime.now(timezone.utc)))
                db.commit()
                made.append(u.nickname)
            _save_auto(db, {"period": d_from.isoformat(), "to": d_to.isoformat(), "running": False,
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "made": made, "skipped": skipped, "errors": errors[:30]})
    except Exception:  # noqa: BLE001 — сбой не должен оставить «идёт сборка» навсегда
        log.exception("Черновики отчётов не собраны")
        with SessionLocal() as db:
            st = _auto_state(db)
            st.update(running=False, errors=(st.get("errors") or []) + ["сбой сборки — смотрите журнал сервера"])
            _save_auto(db, st)
    finally:
        _lock.release()


def _just_started(st: dict) -> bool:
    """Сборка поставлена в очередь, но ещё не взяла замок (или сервер перезапустили посреди сборки — тогда не «идёт»)."""
    if not st.get("running") or not st.get("started_at"):
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(st["started_at"])).total_seconds() < 120
    except ValueError:
        return False


@router.get("/reports/auto")
def reports_auto_status(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Состояние ежемесячных черновиков. Если за прошлый месяц их ещё не собирали — запускает сборку фоном."""
    if not sheets.enabled():
        return {"enabled": False}
    d_from, d_to = report_build.previous_month()
    st = _auto_state(db)
    if st.get("period") != d_from.isoformat() and not _lock.locked():
        st = {"period": d_from.isoformat(), "to": d_to.isoformat(), "running": True,
              "started_at": datetime.now(timezone.utc).isoformat()}
        _save_auto(db, st)
        background.add_task(make_monthly, d_from, d_to)
    drafts = db.scalars(select(Report).where(Report.kind == "auto", Report.status == "draft",
                                             Report.period_from == d_from.isoformat())).all()
    names = {u.id: u.nickname for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in drafts})))} if drafts else {}
    linked = sum(1 for u in db.scalars(select(User).where(User.role != "curator")) if sheets.linked(u))
    return {"enabled": True, "linked": linked, "period": d_from.isoformat(), "to": d_to.isoformat(),
            "label": report_build.period_label(d_from, d_to), "running": _lock.locked() or _just_started(st),
            "made": st.get("made") or [], "skipped": st.get("skipped") or [], "errors": st.get("errors") or [],
            "drafts": [{"report": r.id, "user_id": r.user_id, "nickname": names.get(r.user_id, "?")} for r in drafts]}


@router.post("/reports/auto/run")
def reports_auto_run(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Собрать ещё раз (например, после того как привязали новых учеников): недостающие черновики за прошлый месяц."""
    if not sheets.enabled():
        raise HTTPException(400, "Таблица не подключена (python run.py set-sheet).")
    if _lock.locked():
        return {"running": True}
    d_from, d_to = report_build.previous_month()
    _save_auto(db, {"period": d_from.isoformat(), "to": d_to.isoformat(), "running": True,
                    "started_at": datetime.now(timezone.utc).isoformat()})
    background.add_task(make_monthly, d_from, d_to)
    return {"running": True}
