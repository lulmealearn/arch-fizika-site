"""Публичная часть: список визуализаций, сами визуализации и обложки."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import config, files
from .db import get_db
from .models import Section, Visualization
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
def list_visualizations(db: Session = Depends(get_db)):
    sections = db.scalars(select(Section).order_by(Section.position)).all()
    items = db.scalars(
        select(Visualization).options(joinedload(Visualization.section))
        .where(Visualization.is_published.is_(True)).order_by(Visualization.position, Visualization.id)
    ).all()
    return {"sections": [section_out(s) for s in sections], "items": [viz_public(v) for v in items]}


@router.get("/viz/{name}")
def open_visualization(name: str, request: Request, db: Session = Depends(get_db)):
    if name == "index.html":
        return FileResponse(config.PUBLIC_DIR / "viz" / "index.html")
    if not name.endswith(".html") or not files.safe_name(name):
        raise HTTPException(404, "Нет такой визуализации.")
    v = db.scalar(select(Visualization).where(Visualization.file_name == name))
    if not v or (not v.is_published and not is_admin(request)):
        raise HTTPException(404, "Нет такой визуализации.")
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
