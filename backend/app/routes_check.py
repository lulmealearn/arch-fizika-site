"""Сдача ДЗ и пробников на сайте и проверка кураторами.

Ученик прикрепляет к занятию фото или PDF (пока идёт срок) — это и есть «Сдал». Бот @Arch_Tutor_Bot присылает работу
кураторам (и владельцу, если задан ADMIN_TG_CHAT_ID) со ссылкой на страницу проверки /check/. Куратор ставит
«верно из всего» и комментарий — ученик видит результат в папке занятия.
Куратор — обычный аккаунт с role="curator" (назначает админ во вкладке «Ученики»)."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, deadlines, files, scale, sheets, telegram
from .access import current_user
from .db import SessionLocal, get_db
from .mockcheck import grade
from .models import Lesson, Mock, MockAttempt, Submission, User
from .routes_auth import _my_item, _need_active, attempt_out
from .security import check_same_origin, is_admin
from .serialize import _iso
from .tracking import touch

log = logging.getLogger("check")
router = APIRouter()
MSK = timezone(timedelta(hours=3))  # Москва без перехода на летнее время


# ── Кто проверяет ──
def staff_name(request: Request, db: Session) -> Optional[str]:
    """Ник куратора, «Админ» — для админки в этом браузере, None — не проверяющий."""
    if is_admin(request):
        return "Админ"
    u = current_user(request, db)
    if u is not None and u.role == "curator":
        return u.nickname
    return None


def require_staff(request: Request, db: Session = Depends(get_db)) -> str:
    name = staff_name(request, db)
    if not name:
        raise HTTPException(401, "Страница проверки — только для кураторов. Войдите в личный кабинет под аккаунтом куратора.")
    check_same_origin(request)
    return name


# ── Вывод ──
def files_out(s: Submission) -> List[dict]:
    return [{"url": f"/sub/{s.id}/{f['name']}", "type": f["type"], "name": f.get("orig") or f["name"], "size": f.get("size", 0)}
            for f in (s.files or [])]


def submission_out(s: Optional[Submission]) -> Optional[dict]:
    """Для ученика: что сдал и результат проверки."""
    if s is None:
        return None
    return {"id": s.id, "created_at": _iso(s.created_at), "files": files_out(s), "status": s.status,
            "score": s.score, "max": s.max_score, "comment": s.comment or "", "checked_at": _iso(s.checked_at),
            "task_scores": s.task_scores or None,
            "purged": s.files_purged_at is not None}


def latest_submissions(db: Session, user_id: int, field: str = "lesson_id") -> dict:
    """{lesson_id или mock_id: последняя сдача ученика}."""
    out = {}
    col = getattr(Submission, field)
    for s in db.scalars(select(Submission).where(Submission.user_id == user_id, col.is_not(None))
                        .order_by(Submission.created_at, Submission.id)):
        out[getattr(s, field)] = s
    return out


def purge_old_files(db: Session) -> int:
    """Удалить файлы работ, проверенных больше SUBMISSION_KEEP_DAYS дней назад. Балл и комментарий остаются."""
    if config.SUBMISSION_KEEP_DAYS <= 0:
        return 0
    edge = datetime.now(timezone.utc) - timedelta(days=config.SUBMISSION_KEEP_DAYS)
    old = db.scalars(select(Submission).where(Submission.status == "checked", Submission.files_purged_at.is_(None),
                                              Submission.checked_at < edge)).all()
    for s in old:
        files.delete_submission_files(s.id)
        s.files = []
        s.files_purged_at = datetime.now(timezone.utc)
    if old:
        db.commit()
        log.info("Удалены файлы %d проверенных работ старше %d дней", len(old), config.SUBMISSION_KEEP_DAYS)
    return len(old)


# ── Сдача ──
async def _read(upload: UploadFile) -> bytes:
    data = await upload.read(config.MAX_SUB_FILE_BYTES + 1)
    if len(data) > config.MAX_SUB_FILE_BYTES:
        raise HTTPException(413, f"Файл «{upload.filename}» больше {config.MAX_SUB_FILE_BYTES // (1024 * 1024)} МБ.")
    return data


async def _collect(files_in: List[UploadFile]) -> List[Tuple[bytes, str, str]]:
    uploads = [f for f in files_in if f is not None and f.filename]
    if not uploads:
        raise HTTPException(400, "Прикрепите решение: фото или PDF.")
    if len(uploads) > config.MAX_SUB_FILES:
        raise HTTPException(400, f"Не больше {config.MAX_SUB_FILES} файлов за раз.")
    parts: List[Tuple[bytes, str, str]] = []
    for up in uploads:
        data = await _read(up)
        ext = files.detect_submission(data)
        if not ext:
            raise HTTPException(400, f"«{up.filename}» — не фото и не PDF. Подойдут JPEG, PNG, WebP или PDF.")
        parts.append((data, ext, (up.filename or "")[:120]))
    return parts


def _store(db: Session, s: Submission, parts: List[Tuple[bytes, str, str]], row) -> None:
    """Записать файлы работы на диск и отметить сдачу; при ошибке — откатить и убрать файлы."""
    db.add(s)
    db.flush()
    d = files.submission_dir(s.id)
    d.mkdir(parents=True, exist_ok=True)
    meta = []
    try:
        for i, (data, ext, orig) in enumerate(parts, 1):
            name = f"{i:02d}.{ext}"
            (d / name).write_bytes(data)
            meta.append({"name": name, "orig": orig, "type": files.SUB_TYPES[ext], "size": len(data)})
        s.files = meta
        deadlines.submit(row)
        db.commit()
    except Exception:
        db.rollback()
        files.delete_submission_files(s.id)
        raise


@router.post("/api/me/mocks/{pk}/submission")
async def submit_mock(pk: int, request: Request, background: BackgroundTasks,
                      files_in: List[UploadFile] = File(..., alias="files"), answers: str = Form(""),
                      db: Session = Depends(get_db)):
    """Сдача пробника одной кнопкой: бланк первой части (если есть ключ — проверяется сразу) и решения файлами
    (обычно один PDF, собранный из фото в браузере). Только пока идёт срок."""
    user, m, row = _my_item(request, db, "mocks", pk)
    if deadlines.state(row) == "done":
        raise HTTPException(409, "Этот пробник уже сдан.")
    _need_active(db, row)
    parts = await _collect(files_in)
    attempt = None
    if m.answer_key:
        if db.scalar(select(MockAttempt.id).where(MockAttempt.user_id == user.id, MockAttempt.mock_id == m.id)):
            raise HTTPException(409, "Ответы на этот пробник уже отправлены.")
        try:
            raw = json.loads(answers or "{}")
        except ValueError:
            raise HTTPException(400, "Ответы переданы в неверном виде.")
        allowed = {str(t["n"]) for t in m.answer_key}
        given = {str(k): (str(v) if v is not None else "").strip()[:60] for k, v in (raw or {}).items() if str(k) in allowed}
        score, total, details = grade(m.answer_key, given)
        attempt = MockAttempt(user_id=user.id, mock_id=m.id, answers=given, score=score, max_score=total, details=details)
        db.add(attempt)
    s = Submission(user_id=user.id, mock_id=m.id, files=[], overdue=row.overdue_count or 0)
    _store(db, s, parts, row)
    touch(db, user, request)
    background.add_task(notify_curators, s.id)
    background.add_task(sheets.push_submission, s.id)  # первая часть — сразу в таблицу
    background.add_task(_purge_in_background)
    return {"deadline": deadlines.status_out(row, m), "submission": submission_out(s),
            "result": attempt_out(attempt) if attempt else None}


def _purge_in_background() -> None:
    with SessionLocal() as db:
        purge_old_files(db)


@router.post("/api/me/lessons/{pk}/submission")
async def submit_homework(pk: int, request: Request, background: BackgroundTasks,
                          files_in: List[UploadFile] = File(..., alias="files"), db: Session = Depends(get_db)):
    """Ученик сдаёт ДЗ файлами. Только пока идёт срок; после сдачи занятие «Сдано», кураторам уходит сообщение."""
    user, lesson, row = _my_item(request, db, "lessons", pk)
    if deadlines.state(row) == "done":
        raise HTTPException(409, "Это занятие уже сдано.")
    _need_active(db, row)
    parts = await _collect(files_in)
    s = Submission(user_id=user.id, lesson_id=lesson.id, files=[], overdue=row.overdue_count or 0)
    _store(db, s, parts, row)
    touch(db, user, request)
    background.add_task(notify_curators, s.id)
    background.add_task(sheets.push_submission, s.id)  # «ДЗ сдал» и дата — сразу в таблицу
    background.add_task(_purge_in_background)
    return {"deadline": deadlines.status_out(row, lesson), "submission": submission_out(s)}


# ── Файлы сданных работ ──
@router.get("/sub/{sid}/{name}")
def open_submission_file(sid: int, name: str, request: Request, db: Session = Depends(get_db)):
    """Файл видят сам ученик, кураторы и админ."""
    s = db.get(Submission, sid)
    path = files.submission_path(sid, name)
    if s is None or not path.exists():
        raise HTTPException(404, "Такого файла нет.")
    if not staff_name(request, db):
        u = current_user(request, db)
        if u is None or u.id != s.user_id:
            raise HTTPException(404, "Такого файла нет.")
    meta = next((f for f in (s.files or []) if f["name"] == name), None)
    if meta is None:
        raise HTTPException(404, "Такого файла нет.")
    return FileResponse(path, media_type=meta["type"], headers={
        "Content-Disposition": f'inline; filename="DZ-{sid}-{name}"',
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    })


# ── Страница проверки ──
class CheckIn(BaseModel):
    score: int = 0
    max_score: int = 0
    comment: str = ""
    task_scores: Optional[dict] = None  # пробник: баллы по заданиям второй части


def check_out(s: Submission, u: Optional[User], l: Optional[Lesson], m: Optional[Mock] = None,
              a: Optional[MockAttempt] = None, sc: Optional[dict] = None) -> dict:
    return {
        "total": scale.total(sc, a, s) if (sc and m) else None,
        "student_tg": bool(u and u.tg_chat_id),
        "student_notified_at": _iso(s.student_notified_at), "student_notify_error": s.student_notify_error or "",
        "id": s.id, "student": u.nickname if u else "?", "student_id": s.user_id,
        "kind": "mock" if s.mock_id else "lesson",
        "lesson": {"pk": l.id, "number": l.number, "title": l.title, "hw_url": f"/hw/{l.number}" if l and l.hw_file else None} if l else None,
        "mock": {"pk": m.id, "number": m.number, "title": m.title, "url": f"/mock/{m.number}"} if m else None,
        "part1": {"score": a.score, "max": a.max_score, "wrong": [d["n"] for d in (a.details or []) if d["points"] < d["max"]]} if a else None,
        "purged": s.files_purged_at is not None, "task_scores": s.task_scores or None,
        "created_at": _iso(s.created_at), "overdue": s.overdue or 0, "files": files_out(s),
        "status": s.status, "score": s.score, "max": s.max_score, "comment": s.comment or "",
        "checked_by": s.checked_by, "checked_at": _iso(s.checked_at),
        "notified_at": _iso(s.notified_at), "notify_error": s.notify_error or "",
        "sheet": {"synced_at": _iso(s.sheet_synced_at), "place": s.sheet_place or "", "error": s.sheet_error or ""}
        if sheets.enabled() else None,
    }


@router.get("/api/check/me")
def check_me(response: Response, name: str = Depends(require_staff)):
    response.headers["Cache-Control"] = "no-store"
    return {"name": name, "bot": telegram.enabled()}


@router.get("/api/check/submissions")
def check_list(response: Response, status: str = "new", name: str = Depends(require_staff), db: Session = Depends(get_db)):
    """Очередь: «ждут проверки» — старые сверху (кто раньше сдал), «проверены» — свежие сверху."""
    response.headers["Cache-Control"] = "no-store"
    q = select(Submission)
    if status in ("new", "checked"):
        q = q.where(Submission.status == status)
    q = q.order_by(Submission.created_at.asc() if status == "new" else Submission.created_at.desc(), Submission.id)
    subs = db.scalars(q.limit(300)).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({s.user_id for s in subs})))} if subs else {}
    lessons = {l.id: l for l in db.scalars(select(Lesson).where(Lesson.id.in_({s.lesson_id for s in subs if s.lesson_id})))} if subs else {}
    mocks = {m.id: m for m in db.scalars(select(Mock).where(Mock.id.in_({s.mock_id for s in subs if s.mock_id})))} if subs else {}
    atts = {(a.user_id, a.mock_id): a for a in db.scalars(select(MockAttempt).where(MockAttempt.mock_id.in_(set(mocks))))} if mocks else {}
    counts = {st: len(db.scalars(select(Submission.id).where(Submission.status == st)).all()) for st in ("new", "checked")}
    sc = scale.get(db)
    return {"items": [check_out(s, users.get(s.user_id), lessons.get(s.lesson_id), mocks.get(s.mock_id),
                                atts.get((s.user_id, s.mock_id)), sc) for s in subs],
            "counts": counts, "part2_max": sc["part2_max"], "part2": sc["part2"]}


@router.put("/api/check/submissions/{sid}")
def check_save(sid: int, body: CheckIn, background: BackgroundTasks, name: str = Depends(require_staff), db: Session = Depends(get_db)):
    """Результат проверки: сколько верно из скольких и комментарий. Можно исправить позже."""
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404, "Работа не найдена.")
    ts = None
    if s.mock_id:
        sc = scale.get(db)
        ts = scale.part2_scores(sc, body.task_scores or {})
        body.score, body.max_score = sum(ts.values()), sc["part2_max"]
    if not 1 <= body.max_score <= 500:
        raise HTTPException(400, "«Из скольких» — от 1 до 500.")
    if not 0 <= body.score <= body.max_score:
        raise HTTPException(400, "Баллов не может быть больше максимума." if s.mock_id else "«Верно» — от 0 до числа заданий.")
    edited = s.status == "checked"
    same = (edited and s.score == body.score and s.max_score == body.max_score and (s.task_scores or None) == ts
            and (s.comment or "") == (body.comment or "").strip()[:3000])
    s.score, s.max_score = body.score, body.max_score
    s.task_scores = ts
    s.comment = (body.comment or "").strip()[:3000]
    s.status = "checked"
    s.checked_by = name
    s.checked_at = datetime.now(timezone.utc)
    db.commit()
    if not same:
        background.add_task(notify_student, s.id, edited)  # результат — ученику в Telegram одновременно с сайтом
    if not same or s.sheet_error or not s.sheet_synced_at:
        background.add_task(sheets.push_submission, s.id)  # и в Google-таблицу
    m = db.get(Mock, s.mock_id) if s.mock_id else None
    a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == s.user_id, MockAttempt.mock_id == s.mock_id)) if m else None
    return check_out(s, db.get(User, s.user_id), db.get(Lesson, s.lesson_id) if s.lesson_id else None, m, a, scale.get(db))


@router.post("/api/check/submissions/{sid}/sheet")
def check_sheet_retry(sid: int, name: str = Depends(require_staff), db: Session = Depends(get_db)):
    """«Записать в таблицу ещё раз» — после того как поправили тему или chat id. Ждём ответа скрипта."""
    s = db.get(Submission, sid)
    if s is None:
        raise HTTPException(404, "Работа не найдена.")
    if not sheets.enabled():
        raise HTTPException(400, "Таблица не подключена (python run.py set-sheet).")
    sheets.push_submission(s.id)
    db.expire_all()
    s = db.get(Submission, sid)
    m = db.get(Mock, s.mock_id) if s.mock_id else None
    a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == s.user_id, MockAttempt.mock_id == s.mock_id)) if m else None
    return check_out(s, db.get(User, s.user_id), db.get(Lesson, s.lesson_id) if s.lesson_id else None, m, a, scale.get(db))


# ── Уведомления через бота ──
def _msk(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK).strftime("%d.%m в %H:%M")


def recipients(db: Session) -> List[str]:
    ids = [c for c in db.scalars(select(User.tg_chat_id).where(User.role == "curator", User.tg_chat_id.is_not(None))) if c]
    if config.ADMIN_TG_CHAT_ID and config.ADMIN_TG_CHAT_ID not in ids:
        ids.append(config.ADMIN_TG_CHAT_ID)
    return ids


def notify_curators(sub_id: int) -> None:
    """Фоном после ответа ученику: отправить работу кураторам. Ошибка не мешает сдаче — она видна на странице проверки."""
    with SessionLocal() as db:
        s = db.get(Submission, sub_id)
        if s is None:
            return
        u = db.get(User, s.user_id)
        l = db.get(Lesson, s.lesson_id) if s.lesson_id else None
        m = db.get(Mock, s.mock_id) if s.mock_id else None
        a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == s.user_id, MockAttempt.mock_id == s.mock_id)) if m else None
        to = recipients(db)
        if not telegram.enabled():
            s.notify_error = "Бот не настроен (python run.py set-bot) — работа ждёт на странице проверки."
        elif not to:
            s.notify_error = "Нет кураторов с Telegram chat id — работа ждёт на странице проверки."
        else:
            n_ph = sum(1 for f in s.files if f["type"].startswith("image/"))
            n_pdf = len(s.files) - n_ph
            what = ", ".join(x for x in (f"{n_ph} фото" if n_ph else "", f"{n_pdf} PDF" if n_pdf else "") if x)
            if m:
                title = f"пробник № {m.number}" + (f" «{m.title}»" if m.title else "")
                head = "Новый пробник на проверку"
                extra = f"Первая часть (автопроверка): {a.score} из {a.max_score}\n" if a else ""
            else:
                title = f"занятие № {l.number}" + (f" «{l.title}»" if l.title else "") if l else "занятие"
                head, extra = "Новое ДЗ на проверку", ""
            caption = (f"{head}\n{u.nickname if u else '?'} · {title}\n"
                       f"Сдано {_msk(s.created_at)} (мск) · {what}\n" + extra
                       + (f"До сдачи срок истекал: {s.overdue}\n" if s.overdue else "")
                       + f"Проверить: {config.SITE_URL}/check/#s{s.id}")
            paths = [(files.submission_path(s.id, f["name"]), f["name"]) for f in s.files]
            errors = []
            for chat in to:
                try:
                    telegram.send_files(chat, paths, caption)
                except telegram.TelegramError as e:
                    errors.append(f"{chat}: {e}")
                    log.warning("ДЗ %s не отправлено в %s: %s", s.id, chat, e)
            s.notify_error = "; ".join(errors)[:300]
            if len(errors) < len(to):
                s.notified_at = datetime.now(timezone.utc)
        db.commit()


def student_message(db: Session, s: Submission, edited: bool) -> str:
    """Текст для ученика: то же, что он видит на сайте."""
    head = "Результат исправлен" if edited else "Работа проверена"
    if s.mock_id:
        m = db.get(Mock, s.mock_id)
        a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == s.user_id, MockAttempt.mock_id == s.mock_id))
        lines = [f"{head}: пробник № {m.number}" + (f" «{m.title}»" if m.title else "")]
        if a:
            lines.append(f"Первая часть: {a.score} из {a.max_score} первичных")
        lines.append(f"Вторая часть: {s.score} из {s.max_score} первичных")
        if s.task_scores:
            mx = {str(t["n"]): t["max"] for t in scale.get(db)["part2"]}
            lines.append("  " + ", ".join(f"№{n}: {v}/{mx.get(n, '?')}" for n, v in sorted(s.task_scores.items(), key=lambda x: int(x[0]))))
        t = scale.total(scale.get(db), a, s)
        if t:
            lines.append(f"Итого: {t['primary']} из {t['max']} первичных" + (f" → {t['test']} тестовых" if t["test"] is not None else ""))
        link = f"{config.SITE_URL}/account/#p{m.number}"
    else:
        l = db.get(Lesson, s.lesson_id)
        pct = round(100 * s.score / s.max_score) if s.max_score else 0
        lines = [f"{head}: домашнее задание к занятию № {l.number}" + (f" «{l.title}»" if l.title else ""),
                 f"Верно: {s.score} из {s.max_score} ({pct}%)"]
        link = f"{config.SITE_URL}/account/#z{l.number}"
    if s.comment:
        lines.append(f"Комментарий: {s.comment}")
    lines.append(f"Подробно — в личном кабинете: {link}")
    return "\n".join(lines)


def notify_student(sub_id: int, edited: bool = False) -> None:
    """Фоном после проверки: результат ученику в Telegram (если у него указан chat id)."""
    with SessionLocal() as db:
        s = db.get(Submission, sub_id)
        if s is None or s.status != "checked":
            return
        u = db.get(User, s.user_id)
        if not telegram.enabled():
            s.student_notify_error = "Бот не настроен — результат виден ученику только на сайте."
        elif not (u and u.tg_chat_id):
            s.student_notify_error = "У ученика не указан Telegram chat id — результат виден только на сайте."
        else:
            try:
                telegram.send_text(u.tg_chat_id, student_message(db, s, edited)[:4000])
                s.student_notified_at = datetime.now(timezone.utc)
                s.student_notify_error = ""
            except telegram.TelegramError as e:
                s.student_notify_error = str(e)[:300]
                log.warning("Результат %s не отправлен ученику: %s", s.id, e)
        db.commit()
