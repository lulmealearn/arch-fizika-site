"""Публичная часть: список визуализаций, сами визуализации, обложки и PDF домашних заданий."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import config, files, report_build
from .db import get_db
from .access import can_open, current_user, granted_ids, lesson_unlocked, mock_unlocked, opened_viz_ids
from .tracking import record_view
from .models import Lesson, LessonViz, Mock, Report, Section, Visualization
from .security import is_admin
from .serialize import section_out, viz_public

router = APIRouter()

# Визуализация открывается в «песочнице»: её скрипты работают, но у страницы чужое происхождение,
# поэтому она не может действовать от имени вошедшего админа. localStorage внутри визуализаций недоступен.
VIZ_HEADERS = {
    "Content-Security-Policy": "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox allow-forms allow-modals allow-downloads",
    "Cache-Control": "no-cache",
    "X-Content-Type-Options": "nosniff",
}
COVER_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
}


@router.get("/api/visualizations")
def list_visualizations(request: Request, response: Response, db: Session = Depends(get_db)):
    """Закрытые визуализации тоже в списке (с замком), но открыть их можно только с доступом."""
    response.headers["Cache-Control"] = "private, no-cache"
    sections = db.scalars(select(Section).order_by(Section.position)).all()
    items = db.scalars(
        select(Visualization).options(joinedload(Visualization.section))
        .where(Visualization.is_published.is_(True)).order_by(Visualization.position, Visualization.id)
    ).all()
    admin = is_admin(request)
    user = None if admin else current_user(request, db)
    opened = opened_viz_ids(db, user.id) if user else set()
    out = []
    for v in items:
        d = viz_public(v)
        d["locked"] = d["access"] == "private" and not admin and v.id not in opened
        out.append(d)
    # admin: в этом браузере открыта админка — закрытые открываются без входа, страница об этом предупредит
    return {"sections": [section_out(s) for s in sections], "items": out, "admin": admin}


def _track(db: Session, request: Request, user, kind: str, ref: str, title: str) -> None:
    """Записать, что ученик открыл материал. Админа не считаем: в его браузере ученик может быть тоже залогинен."""
    if user is not None and not is_admin(request):
        record_view(db, user, request, kind, ref, title)


def _to_account(next_path: str, signed_in: bool) -> RedirectResponse:
    """Нет доступа: отправляем в личный кабинет, а оттуда после входа — обратно."""
    q = "next=" + quote(next_path, safe="/")
    if signed_in:
        q += "&locked=1"
    return RedirectResponse("/account/?" + q, status_code=303, headers={"Cache-Control": "no-store"})


def _to_lesson(number: int) -> RedirectResponse:
    """Занятие открыто, но ученик ещё не нажал «Начать»: ведём в папку занятия, там кнопка."""
    return RedirectResponse(f"/account/#z{number}", status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/viz/{name}")
def open_visualization(name: str, request: Request, db: Session = Depends(get_db)):
    if name == "index.html":
        return FileResponse(config.PUBLIC_DIR / "viz" / "index.html")
    if not name.endswith(".html") or not files.safe_name(name):
        raise HTTPException(404, "Нет такой визуализации.")
    v = db.scalar(select(Visualization).where(Visualization.file_name == name))
    if not v or (not v.is_published and not is_admin(request)):
        raise HTTPException(404, "Нет такой визуализации.")
    user = current_user(request, db)
    if v.access == "private" and not can_open(db, request, "viz", v.id, user):
        if user is not None:
            # визуализация из открытого, но ещё не начатого занятия — ведём к кнопке «Начать»
            lessons = granted_ids(db, user.id, "lesson")
            n = db.scalar(select(Lesson.number).join(LessonViz, LessonViz.lesson_id == Lesson.id)
                          .where(LessonViz.viz_id == v.id, Lesson.id.in_(lessons)).limit(1)) if lessons else None
            if n is not None:
                return _to_lesson(n)
        return _to_account(f"/viz/{name}", user is not None)
    path = files.viz_path(name)
    if not path.exists():
        raise HTTPException(404, "Файл визуализации не найден на диске.")
    _track(db, request, user, "viz", v.slug, v.title)
    return FileResponse(path, media_type="text/html; charset=utf-8", headers=VIZ_HEADERS)


@router.get("/covers/{name}")
def open_cover(name: str):
    if not files.safe_name(name):
        raise HTTPException(404)
    media, ok = files.media_type_for(name)
    path = files.cover_path(name)
    if not ok or not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type=media, headers=COVER_HEADERS)


def _lesson_pdf(kind: str, number: int, request: Request, db: Session):
    """PDF занятия по номеру (ДЗ или конспект). Только тем, кому открыто занятие."""
    prefix = "hw" if kind == "hw" else "notes"
    l = db.scalar(select(Lesson).where(Lesson.number == number))
    user = current_user(request, db)
    name = (l.hw_file if kind == "hw" else l.notes_file) if l else None
    if l and user is not None and user.role == "curator":
        return _pdf(name, ("DZ" if kind == "hw" else "Konspekt") + f"-{number}")  # куратору — условие ДЗ для проверки
    if not l or not can_open(db, request, "lesson", l.id, user):
        # не говорим, существует ли занятие: без доступа всё выглядит одинаково
        return _to_account(f"/{prefix}/{number}", user is not None)
    if not lesson_unlocked(db, request, l.id, user):
        return _to_lesson(number)
    out = _pdf(name, ("DZ" if kind == "hw" else "Konspekt") + f"-{number}")
    _track(db, request, user, kind, str(number), l.title)
    return out


def _pdf(name, label: str):
    """Отдать PDF из storage/hw/ для просмотра в браузере."""
    if not name or not files.hw_path(name).exists():
        raise HTTPException(404, "Такого файла нет.")
    return FileResponse(files.hw_path(name), media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{label}.pdf"',
        "Cache-Control": "private, no-cache",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/hw/{number}")
def open_homework(number: int, request: Request, db: Session = Depends(get_db)):
    """ДЗ занятия: /hw/42."""
    return _lesson_pdf("hw", number, request, db)


@router.get("/notes/{number}")
def open_notes(number: int, request: Request, db: Session = Depends(get_db)):
    """Конспект занятия: /notes/42."""
    return _lesson_pdf("notes", number, request, db)


@router.get("/mock/{number}")
def open_mock(number: int, request: Request, db: Session = Depends(get_db)):
    """Пробник: /mock/3. HTML открывается как визуализация (песочница, кнопка «В личный кабинет»), PDF — как PDF."""
    m = db.scalar(select(Mock).where(Mock.number == number))
    user = current_user(request, db)
    curator = m is not None and user is not None and user.role == "curator"  # куратору — вариант для проверки
    if not curator and (not m or not can_open(db, request, "mock", m.id, user)):
        return _to_account(f"/mock/{number}", user is not None)
    if not curator and not mock_unlocked(db, request, m.id, user):
        # пробник открыт, но ученик ещё не нажал «Начать» — ведём к кнопке в кабинете
        return RedirectResponse(f"/account/#p{number}", status_code=303, headers={"Cache-Control": "no-store"})
    _track(db, request, user, "mock", str(number), m.title)
    if m.file_name.endswith(".html"):
        if not files.hw_path(m.file_name).exists():
            raise HTTPException(404, "Такого файла нет.")
        return FileResponse(files.hw_path(m.file_name), media_type="text/html; charset=utf-8",
                            headers={**VIZ_HEADERS, "Cache-Control": "private, no-cache"})
    return _pdf(m.file_name, f"Probnik-{number}")


@router.get("/report/{pk}")
def open_report(pk: int, request: Request, db: Session = Depends(get_db)):
    """Отчёт для родителей — только его ученику и админу."""
    r = db.get(Report, pk)
    user = current_user(request, db)
    admin = is_admin(request)
    if not r or not (admin or (user and user.id == r.user_id and r.status == "published")):
        return _to_account(f"/report/{pk}", user is not None)
    if r.kind == "auto":  # собран из таблицы — страница в вёрстке отчётов, «Сохранить PDF» — печатью браузера
        out = HTMLResponse(report_build.render(r, "admin" if admin else "student"),
                           headers={"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex"})
    else:
        out = _pdf(r.file_name, f"Otchet-{pk}")
    _track(db, request, user, "report", str(pk), r.title)
    return out


@router.get("/watch/{number}")
def watch_lesson(number: int, request: Request, db: Session = Depends(get_db)):
    """Запись занятия: проверяем доступ, отмечаем просмотр и перенаправляем на Телебосс / VK."""
    l = db.scalar(select(Lesson).where(Lesson.number == number))
    user = current_user(request, db)
    if not l or not can_open(db, request, "lesson", l.id, user):
        return _to_account(f"/watch/{number}", user is not None)
    if not lesson_unlocked(db, request, l.id, user):
        return _to_lesson(number)
    if not l.url:
        raise HTTPException(404, "У этого занятия пока нет записи.")
    _track(db, request, user, "video", str(number), l.title)
    return RedirectResponse(l.url, status_code=303, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
