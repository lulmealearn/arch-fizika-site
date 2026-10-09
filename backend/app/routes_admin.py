"""Админка: вход, загрузка, редактирование, порядок, удаление визуализаций."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from . import config, files
from .db import get_db
from .models import Section, Visualization
from .security import (COOKIE_NAME, check_login_rate, clear_login_failures, is_admin, make_session_token,
                       record_login_failure, require_admin, verify_password)
from .serialize import section_out, viz_admin

router = APIRouter(prefix="/api/admin")
guard = [Depends(require_admin)]


class LoginIn(BaseModel):
    password: str


class OrderIn(BaseModel):
    ids: List[int]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/me")
def me(request: Request):
    return {"authenticated": is_admin(request), "configured": bool(config.ADMIN_PASSWORD_HASH)}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    if not config.ADMIN_PASSWORD_HASH:
        raise HTTPException(503, "Пароль админа ещё не задан. Запусти `python run.py set-password`.")
    ip = _client_ip(request)
    check_login_rate(ip)
    if not verify_password(body.password, config.ADMIN_PASSWORD_HASH):
        record_login_failure(ip)
        raise HTTPException(401, "Неверный пароль.")
    clear_login_failures(ip)
    response.set_cookie(
        COOKIE_NAME, make_session_token(), max_age=config.SESSION_DAYS * 86400,
        httponly=True, samesite="strict", secure=config.COOKIE_SECURE, path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


# ── Чтение ──
def _all(db: Session):
    sections = db.scalars(select(Section).order_by(Section.position)).all()
    items = db.scalars(
        select(Visualization).options(joinedload(Visualization.section)).order_by(Visualization.position, Visualization.id)
    ).all()
    return {"sections": [section_out(s) for s in sections], "items": [viz_admin(v) for v in items]}


@router.get("/visualizations", dependencies=guard)
def admin_list(db: Session = Depends(get_db)):
    return _all(db)


# ── Помощники ──
def _parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    seen, out = set(), []
    for part in raw.replace("\n", ",").split(","):
        t = part.strip()[:30]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:10]


def _section(db: Session, slug: str) -> Section:
    s = db.scalar(select(Section).where(Section.slug == slug))
    if not s:
        raise HTTPException(400, "Такого раздела нет.")
    return s


def _flag(value: Optional[str]) -> bool:
    return (value or "").lower() in ("1", "true", "on", "yes")


def _clean_text(value: Optional[str], limit: int, field: str, required: bool = False) -> str:
    v = (value or "").strip()
    if required and not v:
        raise HTTPException(400, f"Поле «{field}» обязательно.")
    if len(v) > limit:
        raise HTTPException(400, f"Поле «{field}» длиннее {limit} символов.")
    return v


# ── Создание ──
@router.post("/visualizations", dependencies=guard, status_code=201)
async def create(
    html: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    section: str = Form(...),
    tags: str = Form(""),
    parts: str = Form(""),
    slug: str = Form(""),
    is_published: str = Form("true"),
    cover: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    title = _clean_text(title, 200, "Название", required=True)
    description = _clean_text(description, 600, "Описание")
    parts = _clean_text(parts, 60, "Объём")
    sec = _section(db, section)
    slug = files.validate_slug(slug) if slug.strip() else files.slugify(title)
    if db.scalar(select(Visualization).where(Visualization.slug == slug)):
        raise HTTPException(409, f"Адрес «{slug}» уже занят другой визуализацией. Укажи другой.")

    text = files.prepare_html(await files.read_limited(html, config.MAX_HTML_BYTES, "HTML-файл"))
    file_name = f"{slug}.html"
    cover_name = await files.save_cover(slug, cover) if cover and cover.filename else None
    files.write_viz(file_name, text)

    last = db.scalar(select(func.max(Visualization.position))) or 0
    v = Visualization(
        slug=slug, title=title, description=description, section_id=sec.id, tags=_parse_tags(tags),
        parts=parts, file_name=file_name, cover_name=cover_name, position=last + 1,
        is_published=_flag(is_published),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return viz_admin(v)


# ── Изменение ──
@router.patch("/visualizations/{pk}", dependencies=guard)
async def update(
    pk: int,
    html: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    section: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    parts: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    is_published: Optional[str] = Form(None),
    cover: Optional[UploadFile] = File(None),
    remove_cover: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    v = db.get(Visualization, pk)
    if not v:
        raise HTTPException(404, "Визуализация не найдена.")

    if title is not None:
        v.title = _clean_text(title, 200, "Название", required=True)
    if description is not None:
        v.description = _clean_text(description, 600, "Описание")
    if parts is not None:
        v.parts = _clean_text(parts, 60, "Объём")
    if section is not None:
        v.section_id = _section(db, section).id
    if tags is not None:
        v.tags = _parse_tags(tags)
    if is_published is not None:
        v.is_published = _flag(is_published)

    if slug is not None and slug.strip() and slug.strip() != v.slug:
        new_slug = files.validate_slug(slug)
        if db.scalar(select(Visualization).where(Visualization.slug == new_slug, Visualization.id != v.id)):
            raise HTTPException(409, f"Адрес «{new_slug}» уже занят.")
        new_file = f"{new_slug}.html"
        files.rename_viz(v.file_name, new_file)
        v.slug, v.file_name = new_slug, new_file

    if html is not None and html.filename:
        files.write_viz(v.file_name, files.prepare_html(await files.read_limited(html, config.MAX_HTML_BYTES, "HTML-файл")))

    if cover is not None and cover.filename:
        new_cover = await files.save_cover(v.slug, cover)
        if v.cover_name and v.cover_name != new_cover:
            files.delete_cover(v.cover_name)
        v.cover_name = new_cover
    elif _flag(remove_cover) and v.cover_name:
        files.delete_cover(v.cover_name)
        v.cover_name = None

    db.commit()
    db.refresh(v)
    return viz_admin(v)


# ── Порядок ──
@router.put("/order", dependencies=guard)
def reorder(body: OrderIn, db: Session = Depends(get_db)):
    items = {v.id: v for v in db.scalars(select(Visualization))}
    if set(body.ids) != set(items):
        raise HTTPException(400, "Список для сортировки не совпадает с базой. Обнови страницу.")
    for pos, pk in enumerate(body.ids):
        items[pk].position = pos
    db.commit()
    return _all(db)


# ── Удаление ──
@router.delete("/visualizations/{pk}", dependencies=guard)
def delete(pk: int, db: Session = Depends(get_db)):
    v = db.get(Visualization, pk)
    if not v:
        raise HTTPException(404, "Визуализация не найдена.")
    files.delete_viz(v.file_name)
    files.delete_cover(v.cover_name)
    db.delete(v)
    db.commit()
    return {"ok": True}
