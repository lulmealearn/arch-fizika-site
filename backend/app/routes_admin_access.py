"""Админка: ученики и ручные доступы, занятия (запись, конспект, ДЗ и визуализации в одной папке)."""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import deadlines, files
from .access import drop_item, item_users, set_item_users, set_user_grants, user_grants
from .db import get_db
from .mockcheck import grade, parse_key
from .models import GRANT_KINDS, Grant, Lesson, Section, LessonProgress, LessonViz, Mock, MockAttempt, MockProgress, Report, User, View, Visit, Visualization
from .tracking import _aware
from .routes_auth import check_password_rules
from .security import hash_password, require_admin
from .serialize import lesson_out, mock_out, report_out, user_out

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

KIND_MODEL = {"viz": Visualization, "lesson": Lesson, "mock": Mock}


class GrantsIn(BaseModel):
    viz: Optional[List[int]] = None
    lesson: Optional[List[int]] = None
    mock: Optional[List[int]] = None


class UsersIn(BaseModel):
    user_ids: List[int]


class PasswordIn(BaseModel):
    password: str


# ── Помощники ──
def _existing_ids(db: Session, model, ids: List[int]) -> List[int]:
    ids = list(set(ids))
    if not ids:
        return []
    found = set(db.scalars(select(model.id).where(model.id.in_(ids))))
    if found != set(ids):
        raise HTTPException(400, "Часть материалов или учеников не найдена. Обновите страницу.")
    return ids


def _user(db: Session, pk: int) -> User:
    u = db.get(User, pk)
    if not u:
        raise HTTPException(404, "Ученик не найден.")
    return u


def _number(value, what: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"Номер {what} — целое число.")
    if not 1 <= n <= 100000:
        raise HTTPException(400, f"Номер {what} — от 1 до 100000.")
    return n


def _title(value: Optional[str]) -> str:
    v = (value or "").strip()
    if len(v) > 200:
        raise HTTPException(400, "Название длиннее 200 символов.")
    return v


def _url(value: Optional[str]) -> str:
    """Ссылка на запись; пустая — записи у занятия нет."""
    v = (value or "").strip()
    if not v:
        return ""
    p = urlparse(v)
    if p.scheme not in ("http", "https") or not p.netloc or len(v) > 1000:
        raise HTTPException(400, "Ссылка на урок должна начинаться с https:// (или http://).")
    return v


def _parse_ids(raw: Optional[str]) -> Optional[List[int]]:
    """Списки id в форме приходят строкой JSON: «[1, 4, 7]»."""
    if raw is None or raw == "":
        return None
    try:
        data = json.loads(raw)
        return [int(x) for x in data]
    except (ValueError, TypeError):
        raise HTTPException(400, "Список передан в неверном виде.")


# ── Ученики ──
@router.get("/users")
def users_list(db: Session = Depends(get_db)):
    grants = user_grants(db)
    users = db.scalars(select(User).order_by(User.nickname_key)).all()
    reports: Dict[int, list] = {}
    for r in db.scalars(select(Report).order_by(Report.created_at.desc(), Report.id.desc())):
        reports.setdefault(r.user_id, []).append(report_out(r))
    # сводка активности: последний заход, сеансы за 30 дней, сделано из открытого
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    last_seen: Dict[int, datetime] = {}
    visits30: Dict[int, int] = {}
    devices30: Dict[int, set] = {}
    for v in db.scalars(select(Visit)):
        seen = _aware(v.last_seen_at)
        if v.user_id not in last_seen or seen > last_seen[v.user_id]:
            last_seen[v.user_id] = seen
        if seen >= month_ago:
            visits30[v.user_id] = visits30.get(v.user_id, 0) + 1
            devices30.setdefault(v.user_id, set()).add(v.device)
    _settle_all(db)
    done_l = _done_map(db, LessonProgress, LessonProgress.lesson_id)
    overdue_l: Dict[int, int] = {}
    active_l: Dict[int, int] = {}
    for p in db.scalars(select(LessonProgress)):
        if p.overdue_count:
            overdue_l[p.user_id] = overdue_l.get(p.user_id, 0) + p.overdue_count
        if deadlines.state(p) == "active":
            active_l[p.user_id] = active_l.get(p.user_id, 0) + 1
    done_m = _done_map(db, MockProgress, MockProgress.mock_id)
    out = []
    for u in users:
        g = grants.get(u.id) or {}
        d = user_out(u, g)
        d["reports"] = reports.get(u.id, [])
        seen = last_seen.get(u.id) or _aware(u.last_login_at)
        d["stats"] = {
            "last_seen_at": seen.isoformat() if seen else None,
            "visits_30d": visits30.get(u.id, 0),
            "devices_30d": len(devices30.get(u.id, ())),
            "lessons_done": len(done_l.get(u.id, set()) & set(g.get("lesson", []))),
            "lessons_total": len(g.get("lesson", [])),
            "lessons_active": active_l.get(u.id, 0),
            "lessons_overdue": overdue_l.get(u.id, 0),
            "mocks_done": len(done_m.get(u.id, set()) & set(g.get("mock", []))),
            "mocks_total": len(g.get("mock", [])),
        }
        out.append(d)
    return {"users": out}


def _settle_all(db: Session) -> None:
    """Истёкшие сроки на ДЗ → «Не начато» с засчитанной просрочкой (до того как считать сводки)."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(LessonProgress).where(LessonProgress.submitted_at.is_(None), LessonProgress.due_at.is_not(None))).all()
    if any([deadlines.settle(p, now) for p in rows]):
        db.commit()


def _done_map(db: Session, model, item_col) -> Dict[int, set]:
    """{user_id: {id отмеченных сделанными}} — для занятий или пробников."""
    out: Dict[int, set] = {}
    for uid, item in db.execute(select(model.user_id, item_col).where(model.done.is_(True))):
        out.setdefault(uid, set()).add(item)
    return out


def _iso(dt) -> Optional[str]:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _attempt_out(a: Optional[MockAttempt]) -> Optional[dict]:
    if a is None:
        return None
    return {"score": a.score, "max": a.max_score, "submitted_at": _iso(a.submitted_at),
            "wrong": [d["n"] for d in (a.details or []) if d["points"] < d["max"]], "details": a.details or []}


@router.get("/users/{pk}/activity")
def user_activity(pk: int, db: Session = Depends(get_db)):
    """Подробно об ученике: сеансы, что открывал, что отмечено сделанным."""
    u = _user(db, pk)
    visits = db.scalars(select(Visit).where(Visit.user_id == u.id).order_by(Visit.started_at.desc(), Visit.id.desc()).limit(60)).all()
    views = db.scalars(select(View).where(View.user_id == u.id).order_by(View.at.desc(), View.id.desc()).limit(300)).all()

    # что открывал за сеанс: просмотры, попавшие в его промежуток
    out_visits = []
    for v in visits:
        a, b = _aware(v.started_at), _aware(v.last_seen_at)
        opened = [w for w in views if a - timedelta(seconds=5) <= _aware(w.at) <= b + timedelta(seconds=5)]
        out_visits.append({
            "started_at": _iso(a), "last_seen_at": _iso(b), "minutes": max(1, round((b - a).total_seconds() / 60)),
            "device": v.device, "opened": len(opened),
        })

    g = user_grants(db).get(u.id) or {}
    lesson_ids, mock_ids = g.get("lesson", []), g.get("mock", [])
    _settle_all(db)
    lp = {p.lesson_id: p for p in db.scalars(select(LessonProgress).where(LessonProgress.user_id == u.id))}
    mp = {p.mock_id: p for p in db.scalars(select(MockProgress).where(MockProgress.user_id == u.id))}
    # последний раз открывал материалы занятия / пробник
    last_open: Dict[str, datetime] = {}
    for w in views:
        key = ("mock:" if w.kind == "mock" else "lesson:" if w.kind in ("video", "notes", "hw") else w.kind + ":") + w.ref
        if key not in last_open:
            last_open[key] = _aware(w.at)
    lessons = db.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids)).order_by(Lesson.number.desc())).all() if lesson_ids else []
    mocks = db.scalars(select(Mock).where(Mock.id.in_(mock_ids)).order_by(Mock.number.desc())).all() if mock_ids else []

    attempts = {a.mock_id: a for a in db.scalars(select(MockAttempt).where(MockAttempt.user_id == u.id))}

    def prog(p):
        when = (p.submitted_at or p.updated_at) if isinstance(p, LessonProgress) else (p.updated_at if p else None)
        return {"done": bool(p and p.done), "marked_at": _iso(when) if p and p.done else None}

    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent = [v for v in visits if _aware(v.last_seen_at) >= month_ago]
    return {
        "user": {"id": u.id, "nickname": u.nickname, "created_at": _iso(u.created_at), "last_login_at": _iso(u.last_login_at)},
        "summary": {
            "visits_30d": len(recent),
            "minutes_30d": sum(max(1, round((_aware(v.last_seen_at) - _aware(v.started_at)).total_seconds() / 60)) for v in recent),
            "devices_30d": sorted({v.device for v in recent}),
            "views_30d": len([w for w in views if _aware(w.at) >= month_ago]),
        },
        "visits": out_visits,
        "views": [{"kind": w.kind, "ref": w.ref, "title": w.title, "at": _iso(w.at)} for w in views[:80]],
        "lessons": [dict(pk=l.id, number=l.number, title=l.title, opened_at=_iso(last_open.get("lesson:" + str(l.number))),
                         deadline=deadlines.status_out(lp.get(l.id), l), **prog(lp.get(l.id))) for l in lessons],
        "mocks": [dict(pk=m.id, number=m.number, title=m.title, opened_at=_iso(last_open.get("mock:" + str(m.number))),
                       result=_attempt_out(attempts.get(m.id)), has_key=bool(m.answer_key), **prog(mp.get(m.id))) for m in mocks],
    }


@router.put("/users/{pk}/grants")
def users_set_grants(pk: int, body: GrantsIn, db: Session = Depends(get_db)):
    """Заменить доступы ученика. Передаются только те виды, которые меняются."""
    u = _user(db, pk)
    for kind in GRANT_KINDS:
        ids = getattr(body, kind)
        if ids is not None:
            set_user_grants(db, u.id, kind, _existing_ids(db, KIND_MODEL[kind], ids))
    db.commit()
    return user_out(u, user_grants(db).get(u.id))


@router.post("/users/{pk}/password")
def users_reset_password(pk: int, body: PasswordIn, db: Session = Depends(get_db)):
    """Новый пароль от админа (восстановления по почте нет). Старые входы ученика сбрасываются."""
    u = _user(db, pk)
    check_password_rules(body.password)
    u.password_hash = hash_password(body.password)
    u.session_version = (u.session_version or 1) + 1
    db.commit()
    return {"ok": True}


@router.delete("/users/{pk}")
def users_delete(pk: int, db: Session = Depends(get_db)):
    u = _user(db, pk)
    db.execute(delete(Grant).where(Grant.user_id == u.id))
    db.execute(delete(LessonProgress).where(LessonProgress.user_id == u.id))
    db.execute(delete(MockProgress).where(MockProgress.user_id == u.id))
    db.execute(delete(MockAttempt).where(MockAttempt.user_id == u.id))
    db.execute(delete(Visit).where(Visit.user_id == u.id))
    db.execute(delete(View).where(View.user_id == u.id))
    for r in db.scalars(select(Report).where(Report.user_id == u.id)).all():
        files.delete_hw(r.file_name)
        db.delete(r)
    db.delete(u)
    db.commit()
    return {"ok": True}


# ── Доступ к одному материалу: кому открыт ──
@router.delete("/users/{pk}/lessons/{lesson_pk}/deadline")
def users_reset_deadline(pk: int, lesson_pk: int, db: Session = Depends(get_db)):
    """Сбросить срок по занятию: снова «Не начато», без засчитанных просрочек (если ученик нажал «Сдал» по ошибке и т. п.)."""
    u = _user(db, pk)
    db.execute(delete(LessonProgress).where(LessonProgress.user_id == u.id, LessonProgress.lesson_id == lesson_pk))
    db.commit()
    return {"ok": True}


@router.put("/access/{kind}/{item_id}")
def access_set(kind: str, item_id: int, body: UsersIn, db: Session = Depends(get_db)):
    if kind not in KIND_MODEL:
        raise HTTPException(404)
    if not db.get(KIND_MODEL[kind], item_id):
        raise HTTPException(404, "Материал не найден.")
    set_item_users(db, kind, item_id, _existing_ids(db, User, body.user_ids))
    db.commit()
    return {"user_ids": sorted(item_users(db, kind).get(item_id, []))}


# ── Занятия ──
def _lesson_viz(db: Session) -> Dict[int, List[int]]:
    out: Dict[int, List[int]] = {}
    for lv in db.scalars(select(LessonViz).order_by(LessonViz.position, LessonViz.id)):
        out.setdefault(lv.lesson_id, []).append(lv.viz_id)
    return out


def _lesson_json(db: Session, l: Lesson) -> dict:
    return lesson_out(l, item_users(db, "lesson").get(l.id, []), _lesson_viz(db).get(l.id, []))


def set_lesson_viz(db: Session, lesson_id: int, viz_ids: List[int]) -> None:
    """Состав визуализаций в папке занятия, порядок — как прислали."""
    ids = []
    for v in viz_ids:
        if v not in ids:
            ids.append(v)
    _existing_ids(db, Visualization, ids)
    db.execute(delete(LessonViz).where(LessonViz.lesson_id == lesson_id))
    for pos, vid in enumerate(ids):
        db.add(LessonViz(lesson_id=lesson_id, viz_id=vid, position=pos))


def _apply_section(db: Session, l: Lesson, value: str) -> None:
    """value: slug раздела, «none» — без раздела, «auto» — раздел первой визуализации в папке."""
    value = (value or "auto").strip()
    if value == "none":
        l.section_id = None
    elif value == "auto":
        l.section_id = db.scalar(select(Visualization.section_id).join(LessonViz, LessonViz.viz_id == Visualization.id)
                                 .where(LessonViz.lesson_id == l.id).order_by(LessonViz.position, LessonViz.id).limit(1))
    else:
        s = db.scalar(select(Section).where(Section.slug == value))
        if not s:
            raise HTTPException(400, "Такого раздела нет.")
        l.section_id = s.id


def _deadline_days(value: Optional[str]) -> Optional[int]:
    """Срок на ДЗ в днях; пусто или по умолчанию — None (тогда deadlines.DEFAULT_DAYS)."""
    v = (value or "").strip()
    if not v:
        return None
    try:
        n = int(v)
    except ValueError:
        raise HTTPException(400, "Срок на ДЗ — целое число дней.")
    if not 1 <= n <= deadlines.MAX_DAYS:
        raise HTTPException(400, f"Срок на ДЗ — от 1 до {deadlines.MAX_DAYS} дней.")
    return None if n == deadlines.DEFAULT_DAYS else n


def _lesson_number_free(db: Session, number: int, pk: Optional[int] = None) -> None:
    q = select(Lesson.id).where(Lesson.number == number)
    if pk is not None:
        q = q.where(Lesson.id != pk)
    if db.scalar(q):
        raise HTTPException(409, f"Занятие № {number} уже есть. Измените его или выберите другой номер.")


@router.get("/lessons")
def lessons_list(db: Session = Depends(get_db)):
    who, viz = item_users(db, "lesson"), _lesson_viz(db)
    lessons = db.scalars(select(Lesson).order_by(Lesson.number.desc())).all()
    return {"items": [lesson_out(l, who.get(l.id, []), viz.get(l.id, [])) for l in lessons]}


@router.post("/lessons", status_code=201)
async def lessons_create(
    number: str = Form(...), title: str = Form(""), url: str = Form(""), section: Optional[str] = Form(None),
    user_ids: Optional[str] = Form(None), viz_ids: Optional[str] = Form(None), deadline_days: Optional[str] = Form(None),
    notes: Optional[UploadFile] = File(None), hw: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    n = _number(number, "занятия")
    _lesson_number_free(db, n)
    users, vizs = _parse_ids(user_ids), _parse_ids(viz_ids)
    l = Lesson(number=n, title=_title(title), url=_url(url), deadline_days=_deadline_days(deadline_days))
    if notes is not None and notes.filename:
        l.notes_file = await files.save_lesson_pdf("notes", n, notes)
    if hw is not None and hw.filename:
        l.hw_file = await files.save_lesson_pdf("hw", n, hw)
    db.add(l)
    db.flush()
    if vizs:
        set_lesson_viz(db, l.id, vizs)
    db.flush()
    _apply_section(db, l, section or "auto")
    if users:
        set_item_users(db, "lesson", l.id, _existing_ids(db, User, users))
    db.commit()
    return _lesson_json(db, l)


async def _replace_pdf(kind: str, l: Lesson, upload: Optional[UploadFile], remove: Optional[str]) -> None:
    attr = "notes_file" if kind == "notes" else "hw_file"
    old = getattr(l, attr)
    if upload is not None and upload.filename:
        new = await files.save_lesson_pdf(kind, l.number, upload)
        if old and old != new:
            files.delete_hw(old)
        setattr(l, attr, new)
    elif (remove or "").lower() in ("1", "true", "yes") and old:
        files.delete_hw(old)
        setattr(l, attr, None)


@router.patch("/lessons/{pk}")
async def lessons_update(
    pk: int, number: Optional[str] = Form(None), title: Optional[str] = Form(None), url: Optional[str] = Form(None),
    section: Optional[str] = Form(None), deadline_days: Optional[str] = Form(None),
    user_ids: Optional[str] = Form(None), viz_ids: Optional[str] = Form(None),
    notes: Optional[UploadFile] = File(None), hw: Optional[UploadFile] = File(None),
    remove_notes: Optional[str] = Form(None), remove_hw: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    l = db.get(Lesson, pk)
    if not l:
        raise HTTPException(404, "Занятие не найдено.")
    if number is not None:
        n = _number(number, "занятия")
        _lesson_number_free(db, n, l.id)
        l.number = n
    if title is not None:
        l.title = _title(title)
    if url is not None:
        l.url = _url(url)
    if deadline_days is not None:
        l.deadline_days = _deadline_days(deadline_days)  # идущие сроки не меняются, новый срок — со следующего «Начать»
    await _replace_pdf("notes", l, notes, remove_notes)
    await _replace_pdf("hw", l, hw, remove_hw)
    vizs, users = _parse_ids(viz_ids), _parse_ids(user_ids)
    if vizs is not None:
        set_lesson_viz(db, l.id, vizs)
    db.flush()
    if section is not None:
        _apply_section(db, l, section)
    if users is not None:
        set_item_users(db, "lesson", l.id, _existing_ids(db, User, users))
    db.commit()
    return _lesson_json(db, l)


@router.delete("/lessons/{pk}")
def lessons_delete(pk: int, db: Session = Depends(get_db)):
    l = db.get(Lesson, pk)
    if not l:
        raise HTTPException(404, "Занятие не найдено.")
    files.delete_hw(l.notes_file)
    files.delete_hw(l.hw_file)
    drop_item(db, "lesson", l.id)
    db.execute(delete(LessonViz).where(LessonViz.lesson_id == l.id))
    db.execute(delete(LessonProgress).where(LessonProgress.lesson_id == l.id))
    db.delete(l)
    db.commit()
    return {"ok": True}


# ── Пробники ──
def _mock_number_free(db: Session, number: int, pk: Optional[int] = None) -> None:
    q = select(Mock.id).where(Mock.number == number)
    if pk is not None:
        q = q.where(Mock.id != pk)
    if db.scalar(q):
        raise HTTPException(409, f"Пробник № {number} уже есть. Измените его или выберите другой номер.")


def _mock_json(db: Session, m: Mock) -> dict:
    return mock_out(m, item_users(db, "mock").get(m.id, []))


def _set_key(db: Session, m: Mock, text: Optional[str]) -> None:
    """Задать ключ первой части. Если ученики уже сдали ответы — пересчитать их результаты по новому ключу."""
    key = parse_key(text) if text and text.strip() else None
    if key == m.answer_key:
        return
    m.answer_key = key
    for a in db.scalars(select(MockAttempt).where(MockAttempt.mock_id == m.id)).all():
        a.score, a.max_score, a.details = grade(key or [], a.answers or {})


@router.get("/mocks")
def mocks_list(db: Session = Depends(get_db)):
    who = item_users(db, "mock")
    return {"items": [mock_out(m, who.get(m.id, [])) for m in db.scalars(select(Mock).order_by(Mock.number.desc()))]}


@router.post("/mocks", status_code=201)
async def mocks_create(
    number: str = Form(...), title: str = Form(""), user_ids: Optional[str] = Form(None),
    answer_key: Optional[str] = Form(None), pdf: UploadFile = File(...), db: Session = Depends(get_db),
):
    n = _number(number, "пробника")
    _mock_number_free(db, n)
    users = _parse_ids(user_ids)
    if answer_key and answer_key.strip():
        parse_key(answer_key)  # проверить до сохранения файла
    name, key_from_html = await files.save_mock_file("mock", n, pdf)
    m = Mock(number=n, title=_title(title), file_name=name)
    db.add(m)
    db.flush()
    # ключ: вписанный в админке важнее, иначе — из HTML пробника
    _set_key(db, m, answer_key if answer_key and answer_key.strip() else key_from_html)
    if users:
        set_item_users(db, "mock", m.id, _existing_ids(db, User, users))
    db.commit()
    return _mock_json(db, m)


@router.patch("/mocks/{pk}")
async def mocks_update(
    pk: int, number: Optional[str] = Form(None), title: Optional[str] = Form(None), user_ids: Optional[str] = Form(None),
    answer_key: Optional[str] = Form(None), clear_key: Optional[str] = Form(None),
    pdf: Optional[UploadFile] = File(None), db: Session = Depends(get_db),
):
    m = db.get(Mock, pk)
    if not m:
        raise HTTPException(404, "Пробник не найден.")
    if number is not None:
        n = _number(number, "пробника")
        _mock_number_free(db, n, m.id)
        m.number = n
    if title is not None:
        m.title = _title(title)
    if answer_key is not None and answer_key.strip():
        parse_key(answer_key)
    key_from_html = None
    if pdf is not None and pdf.filename:
        new, key_from_html = await files.save_mock_file("mock", m.number, pdf)
        if new != m.file_name:
            files.delete_hw(m.file_name)
        m.file_name = new
    if answer_key is not None and answer_key.strip():
        _set_key(db, m, answer_key)
    elif key_from_html:
        _set_key(db, m, key_from_html)
    elif (clear_key or "").lower() in ("1", "true", "yes"):
        _set_key(db, m, None)  # пустая строка в форме приходит как «не прислано», поэтому очистка — отдельным флагом
    users = _parse_ids(user_ids)
    if users is not None:
        set_item_users(db, "mock", m.id, _existing_ids(db, User, users))
    db.commit()
    return _mock_json(db, m)


@router.delete("/mocks/{pk}/attempts/{user_id}")
def mocks_reset_attempt(pk: int, user_id: int, db: Session = Depends(get_db)):
    """Разрешить ученику сдать ответы заново (например, отправил по ошибке)."""
    a = db.scalar(select(MockAttempt).where(MockAttempt.mock_id == pk, MockAttempt.user_id == user_id))
    if not a:
        raise HTTPException(404, "Ответов этого ученика нет.")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.delete("/mocks/{pk}")
def mocks_delete(pk: int, db: Session = Depends(get_db)):
    m = db.get(Mock, pk)
    if not m:
        raise HTTPException(404, "Пробник не найден.")
    files.delete_hw(m.file_name)
    files.delete_hw(m.solutions_file)
    drop_item(db, "mock", m.id)
    db.execute(delete(MockProgress).where(MockProgress.mock_id == m.id))
    db.execute(delete(MockAttempt).where(MockAttempt.mock_id == m.id))
    db.delete(m)
    db.commit()
    return {"ok": True}


# ── Отчёты для родителей: личные PDF ученика ──
@router.post("/users/{pk}/reports", status_code=201)
async def reports_create(pk: int, title: str = Form(...), pdf: UploadFile = File(...), db: Session = Depends(get_db)):
    u = _user(db, pk)
    t = _title(title)
    if not t:
        raise HTTPException(400, "Укажите период, например «Октябрь 2026».")
    name = await files.save_lesson_pdf("report", u.id, pdf)
    if db.scalar(select(Report.id).where(Report.file_name == name)):
        raise HTTPException(409, "Этот файл уже загружен этому ученику.")
    r = Report(user_id=u.id, title=t, file_name=name)
    db.add(r)
    db.commit()
    return report_out(r)


@router.delete("/reports/{pk}")
def reports_delete(pk: int, db: Session = Depends(get_db)):
    r = db.get(Report, pk)
    if not r:
        raise HTTPException(404, "Отчёт не найден.")
    files.delete_hw(r.file_name)
    db.delete(r)
    db.commit()
    return {"ok": True}
