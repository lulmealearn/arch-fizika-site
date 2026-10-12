from typing import Any, Dict, List, Optional

from .models import Homework, Lesson, Section, User, Visualization


def section_out(s: Section) -> Dict[str, Any]:
    return {"id": s.slug, "label": s.label, "color": s.color, "tint": s.tint, "ink": s.ink}


def viz_public(v: Visualization) -> Dict[str, Any]:
    """Тот же формат, что был в data/visualizations.json, чтобы страница хранилища не менялась."""
    return {
        "id": v.slug,
        "title": v.title,
        "description": v.description,
        "section": v.section.slug,
        "tags": list(v.tags or []),
        "parts": v.parts,
        "file": v.file_name,
        "cover": f"covers/{v.cover_name}" if v.cover_name else None,
        "access": v.access or "free",
    }


def viz_admin(v: Visualization, user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    out = viz_public(v)
    out.update({
        "user_ids": sorted(user_ids or []),
        "pk": v.id,
        "slug": v.slug,
        "position": v.position,
        "is_published": v.is_published,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    })
    return out


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def hw_out(h: Homework, user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    out = {"pk": h.id, "number": h.number, "title": h.title, "url": f"/hw/{h.number}", "created_at": _iso(h.created_at)}
    if user_ids is not None:
        out["user_ids"] = sorted(user_ids)
    return out


def lesson_out(l: Lesson, user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    out = {"pk": l.id, "number": l.number, "title": l.title, "url": l.url, "created_at": _iso(l.created_at)}
    if user_ids is not None:
        out["user_ids"] = sorted(user_ids)
    return out


def user_out(u: User, grants: Optional[Dict[str, List[int]]] = None) -> Dict[str, Any]:
    g = grants or {}
    return {
        "id": u.id, "nickname": u.nickname,
        "created_at": _iso(u.created_at), "last_login_at": _iso(u.last_login_at),
        "grants": {k: sorted(g.get(k, [])) for k in ("viz", "hw", "lesson")},
    }
