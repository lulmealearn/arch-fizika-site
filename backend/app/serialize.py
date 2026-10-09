from typing import Any, Dict

from .models import Section, Visualization


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
    }


def viz_admin(v: Visualization) -> Dict[str, Any]:
    out = viz_public(v)
    out.update({
        "pk": v.id,
        "slug": v.slug,
        "position": v.position,
        "is_published": v.is_published,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    })
    return out
