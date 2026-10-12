"""Публичная часть: список визуализаций, сами визуализации, обложки и PDF домашних заданий."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import config, files
from .db import get_db
from .access import can_open, current_user, granted_ids
from .models import Homework, Section, Visualization
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
    opened = granted_ids(db, user.id, "viz") if user else set()
    out = []
    for v in items:
        d = viz_public(v)
        d["locked"] = d["access"] == "private" and not admin and v.id not in opened
        out.append(d)
    return {"sections": [section_out(s) for s in sections], "items": out}


def _to_account(next_path: str, signed_in: bool) -> RedirectResponse:
    """Нет доступа: отправляем в личный кабинет, а оттуда после входа — обратно."""
    q = "next=" + quote(next_path, safe="/")
    if signed_in:
        q += "&locked=1"
    return RedirectResponse("/account/?" + q, status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/viz/{name}")
def open_visualization(name: str, request: Request, db: Session = Depends(get_db)):
    if name == "index.html":
        return FileResponse(config.PUBLIC_DIR / "viz" / "index.html")
    if not name.endswith(".html") or not files.safe_name(name):
        raise HTTPException(404, "Нет такой визуализации.")
    v = db.scalar(select(Visualization).where(Visualization.file_name == name))
    if not v or (not v.is_published and not is_admin(request)):
        raise HTTPException(404, "Нет такой визуализации.")
    if v.access == "private":
        user = current_user(request, db)
        if not can_open(db, request, "viz", v.id, user):
            return _to_account(f"/viz/{name}", user is not None)
    path = files.viz_path(name)
    if not path.exists():
        raise HTTPException(404, "Файл визуализации не найден на диске.")
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


@router.get("/hw/{number}")
def open_homework(number: int, request: Request, db: Session = Depends(get_db)):
    """PDF домашнего задания по номеру: /hw/42. Только тем, кому оно открыто."""
    h = db.scalar(select(Homework).where(Homework.number == number))
    user = current_user(request, db)
    if not h or not can_open(db, request, "hw", h.id, user):
        # не говорим, существует ли задание: без доступа всё выглядит одинаково
        return _to_account(f"/hw/{number}", user is not None)
    path = files.hw_path(h.file_name)
    if not path.exists():
        raise HTTPException(404, "Файл задания не найден на диске.")
    return FileResponse(path, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="DZ-{number}.pdf"',
        "Cache-Control": "private, no-cache",
        "X-Content-Type-Options": "nosniff",
    })
