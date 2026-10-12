from datetime import timezone
from typing import Any, Dict, List, Optional

from .mockcheck import key_to_text
from .models import Lesson, Mock, Report, Section, User, Visualization


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
        "created_at": _iso(v.created_at),
        "updated_at": _iso(v.updated_at),
    })
    return out


def _iso(dt) -> Optional[str]:
    """Время с часовым поясом: SQLite отдаёт его без пояса, а хранится UTC — иначе браузер сдвинет на 3 часа."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def lesson_files(l: Lesson) -> Dict[str, Any]:
    """Ссылки на PDF занятия: открываются по номеру, сервер проверяет доступ."""
    return {
        "notes_url": f"/notes/{l.number}" if l.notes_file else None,
        "hw_url": f"/hw/{l.number}" if l.hw_file else None,
    }


def lesson_out(l: Lesson, user_ids: Optional[List[int]] = None, viz_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """Занятие для админки: всё содержимое папки и кому оно открыто."""
    out = {"pk": l.id, "number": l.number, "title": l.title, "url": l.url or "", "created_at": _iso(l.created_at)}
    out.update(lesson_files(l))
    out["viz_ids"] = list(viz_ids or [])
    out["user_ids"] = sorted(user_ids or [])
    return out


def mock_out(m: Mock, user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """Пробник. С user_ids — для админки (там же текст ключа); без — для ученика (только номера заданий)."""
    key = m.answer_key or []
    out = {"pk": m.id, "number": m.number, "title": m.title, "url": f"/mock/{m.number}", "created_at": _iso(m.created_at),
           "tasks": [t["n"] for t in key]}
    if user_ids is not None:
        out["user_ids"] = sorted(user_ids)
        out["key_text"] = key_to_text(key)
        out["key_points"] = sum(t["points"] for t in key)
    return out


def report_out(r: Report) -> Dict[str, Any]:
    return {"pk": r.id, "title": r.title, "url": f"/report/{r.id}", "created_at": _iso(r.created_at)}


def user_out(u: User, grants: Optional[Dict[str, List[int]]] = None) -> Dict[str, Any]:
    g = grants or {}
    return {
        "id": u.id, "nickname": u.nickname,
        "created_at": _iso(u.created_at), "last_login_at": _iso(u.last_login_at),
        "grants": {k: sorted(g.get(k, [])) for k in ("viz", "lesson", "mock")},
    }
