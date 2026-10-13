"""Запуск: создать таблицы, синхронизировать разделы с seed/ и залить стартовые визуализации в пустую базу."""
import json

from sqlalchemy import delete, func, inspect, select, text

from . import config, files
from .db import Base, SessionLocal, engine
from .models import Grant, Homework, Lesson, LessonProgress, LessonViz, MockProgress, Section, User, Visualization
from .tracking import prune

# Старые разделы → новые. Визуализации переезжают, старые разделы удаляются.
SECTION_REMAP = {
    "kinematika": "mekhanika",
    "dinamika": "mekhanika",
    "elektrostatika": "elektrodinamika",
    "tok": "elektrodinamika",
    "termodinamika": "mkt-termodinamika",
}


def _sync_sections(db, wanted):
    """Разделы из seed/ — источник правды: создаёт недостающие, обновляет названия, цвета и порядок."""
    existing = {s.slug: s for s in db.scalars(select(Section))}
    for i, s in enumerate(wanted):
        row = existing.get(s["id"])
        if row is None:
            row = Section(slug=s["id"])
            db.add(row)
        row.label, row.color, row.tint, row.ink, row.position = s["label"], s["color"], s["tint"], s["ink"], i
    db.flush()

    by_slug = {s.slug: s for s in db.scalars(select(Section))}
    for old, new in SECTION_REMAP.items():
        if old in by_slug and new in by_slug:
            for v in db.scalars(select(Visualization).where(Visualization.section_id == by_slug[old].id)).all():
                v.section = by_slug[new]
            for l in db.scalars(select(Lesson).where(Lesson.section_id == by_slug[old].id)).all():
                l.section_id = by_slug[new].id
            db.flush()
            db.expire(by_slug[old])
            db.delete(by_slug[old])
    db.commit()


# create_all не меняет существующие таблицы: новые колонки добавляем сами (SQL одинаков для SQLite и MySQL)
NEW_COLUMNS = [
    ("visualizations", "access", "VARCHAR(10) NOT NULL DEFAULT 'free'"),
    ("lessons", "notes_file", "VARCHAR(160) NULL"),
    ("lessons", "hw_file", "VARCHAR(160) NULL"),
    ("mocks", "answer_key", "TEXT NULL"),
    ("lessons", "section_id", "INTEGER NULL"),  # JSON-строка (ключ автопроверки)
    ("lessons", "deadline_days", "INTEGER NULL"),
    ("lesson_progress", "first_started_at", "DATETIME NULL"),
    ("lesson_progress", "started_at", "DATETIME NULL"),
    ("lesson_progress", "due_at", "DATETIME NULL"),
    ("lesson_progress", "submitted_at", "DATETIME NULL"),
    ("lesson_progress", "overdue_count", "INTEGER NOT NULL DEFAULT 0"),
    ("lesson_progress", "last_overdue_at", "DATETIME NULL"),
    ("mocks", "deadline_days", "INTEGER NULL"),
    ("mock_progress", "first_started_at", "DATETIME NULL"),
    ("mock_progress", "started_at", "DATETIME NULL"),
    ("mock_progress", "due_at", "DATETIME NULL"),
    ("mock_progress", "submitted_at", "DATETIME NULL"),
    ("mock_progress", "overdue_count", "INTEGER NOT NULL DEFAULT 0"),
    ("mock_progress", "last_overdue_at", "DATETIME NULL"),
    ("users", "role", "VARCHAR(16) NOT NULL DEFAULT 'student'"),
    ("users", "tg_chat_id", "VARCHAR(32) NULL"),
    ("submissions", "mock_id", "INTEGER NULL"),
    ("submissions", "files_purged_at", "DATETIME NULL"),
    ("submissions", "student_notified_at", "DATETIME NULL"),
    ("submissions", "task_scores", "JSON NULL"),
    ("submissions", "student_notify_error", "VARCHAR(300) NOT NULL DEFAULT ''"),
    ("users", "sheet_tab", "VARCHAR(100) NULL"),
    ("submissions", "sheet_synced_at", "DATETIME NULL"),
    ("submissions", "sheet_place", "VARCHAR(160) NOT NULL DEFAULT ''"),
    ("submissions", "sheet_row", "INTEGER NULL"),
    ("submissions", "sheet_error", "VARCHAR(400) NOT NULL DEFAULT ''"),
    ("reports", "kind", "VARCHAR(8) NOT NULL DEFAULT 'pdf'"),
    ("reports", "status", "VARCHAR(12) NOT NULL DEFAULT 'published'"),
    ("reports", "period_from", "VARCHAR(10) NULL"),
    ("reports", "period_to", "VARCHAR(10) NULL"),
    ("reports", "data", "JSON NULL"),
    ("reports", "comment", "TEXT NULL"),
    ("reports", "collected_at", "DATETIME NULL"),
    ("reports", "published_at", "DATETIME NULL"),
    ("reports", "notify_error", "VARCHAR(300) NOT NULL DEFAULT ''"),
]


def _add_missing_columns() -> None:
    insp = inspect(engine)
    for table, column, ddl in NEW_COLUMNS:
        if column not in {c["name"] for c in insp.get_columns(table)}:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            print(f"[db] Добавлена колонка {table}.{column}")


def _migrate_homeworks(db) -> None:
    """Раньше ДЗ было отдельным материалом. Теперь ДЗ лежит в папке занятия с тем же номером:
    файл переезжает в занятие (создаётся, если его не было), доступы к ДЗ становятся доступами к занятию."""
    hws = db.scalars(select(Homework)).all()
    for h in hws:
        lesson = db.scalar(select(Lesson).where(Lesson.number == h.number))
        if lesson is None:
            lesson = Lesson(number=h.number, title=h.title or "", url="")
            db.add(lesson)
            db.flush()
        if not lesson.hw_file:
            lesson.hw_file = h.file_name
        for g in db.scalars(select(Grant).where(Grant.kind == "hw", Grant.item_id == h.id)).all():
            exists = db.scalar(select(Grant.id).where(
                Grant.user_id == g.user_id, Grant.kind == "lesson", Grant.item_id == lesson.id))
            if exists:
                db.delete(g)
            else:
                g.kind, g.item_id = "lesson", lesson.id
            db.flush()  # autoflush выключен: следующий запрос должен видеть эту правку
        db.delete(h)
        db.flush()
    db.commit()
    if hws:
        print(f"[db] ДЗ перенесены в занятия: {len(hws)}")


def _fill_lesson_sections(db) -> None:
    """Занятиям без раздела ставим раздел первой визуализации в их папке (один раз, дальше — как задал админ)."""
    for l in db.scalars(select(Lesson).where(Lesson.section_id.is_(None))).all():
        first = db.scalar(select(Visualization.section_id).join(LessonViz, LessonViz.viz_id == Visualization.id)
                          .where(LessonViz.lesson_id == l.id).order_by(LessonViz.position, LessonViz.id).limit(1))
        if first:
            l.section_id = first
    db.commit()


def _migrate_viewed_to_submitted(db) -> None:
    """Раньше ученик сам отмечал занятие «просмотрено», а пробник «решён». Теперь вместо этого срок (deadlines.py):
    старые отметки считаем сданными, чтобы прошлое не покраснело разом, и начатыми — чтобы материалы остались открыты.
    Повторный запуск ничего не меняет."""
    for model in (LessonProgress, MockProgress):
        for p in db.scalars(select(model).where(model.done.is_(True), model.submitted_at.is_(None))).all():
            p.submitted_at = p.updated_at
        for p in db.scalars(select(model).where(model.submitted_at.is_not(None), model.first_started_at.is_(None))).all():
            p.first_started_at = p.submitted_at
    db.commit()


def _submissions_lesson_nullable() -> None:
    """Первая версия таблицы submissions была только для ДЗ (lesson_id NOT NULL). Теперь туда же сдаются пробники —
    пересобираем таблицу с теми же данными. Нужно лишь базам, созданным до этого изменения (13.10.2026)."""
    insp = inspect(engine)
    if "submissions" not in insp.get_table_names():
        return
    col = next((c for c in insp.get_columns("submissions") if c["name"] == "lesson_id"), None)
    if col is None or col.get("nullable", True):
        return
    from .models import Submission
    old_cols = [c["name"] for c in insp.get_columns("submissions")]
    keep = [c.name for c in Submission.__table__.columns if c.name in old_cols]
    names = ", ".join(keep)
    with engine.begin() as conn:
        for ix in insp.get_indexes("submissions"):
            if engine.dialect.name == "mysql":
                conn.execute(text(f"DROP INDEX {ix['name']} ON submissions"))
            else:
                conn.execute(text(f"DROP INDEX {ix['name']}"))
        conn.execute(text("ALTER TABLE submissions RENAME TO submissions_old"))
        Submission.__table__.create(conn)
        conn.execute(text(f"INSERT INTO submissions ({names}) SELECT {names} FROM submissions_old"))
        conn.execute(text("DROP TABLE submissions_old"))
    print("[db] Таблица submissions пересобрана: теперь в неё сдаются и пробники")


def _drop_curator_deadlines(db) -> None:
    """У кураторов сроков нет (им всё открыто сразу): старые сроки, взятые до назначения куратором, убираем."""
    ids = list(db.scalars(select(User.id).where(User.role == "curator")))
    if ids:
        db.execute(delete(LessonProgress).where(LessonProgress.user_id.in_(ids)))
        db.execute(delete(MockProgress).where(MockProgress.user_id.in_(ids)))
        db.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _submissions_lesson_nullable()
    with SessionLocal() as db:
        _migrate_homeworks(db)
        prune(db)  # журнал активности старше года не храним
        _fill_lesson_sections(db)
        _migrate_viewed_to_submitted(db)
        _drop_curator_deadlines(db)
        from .routes_check import purge_old_files
        purge_old_files(db)  # файлы давно проверенных работ
    seed_file = config.SEED_DIR / "visualizations.json"
    if not seed_file.exists():
        return
    data = json.loads(seed_file.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        _sync_sections(db, data.get("sections", []))

        _import_new_seed_items(db, data.get("items", []))


def _import_new_seed_items(db, items) -> None:
    """Добавляет стартовые визуализации, которых ещё не было. Список уже импортированных хранится
    в storage/seeded.txt, поэтому удалённая через админку визуализация не вернётся сама."""
    marker = config.STORAGE_DIR / "seeded.txt"
    existing = {v.slug for v in db.scalars(select(Visualization))}
    if marker.exists():
        seeded = set(marker.read_text(encoding="utf-8").split())
    else:
        seeded = existing.copy()  # первая проверка на старой базе: всё, что уже есть, считаем импортированным
    sections = {s.slug: s for s in db.scalars(select(Section))}
    last = db.scalar(select(func.max(Visualization.position)))
    pos = -1 if last is None else last
    added = 0
    for item in items:
        slug = item["id"]
        if slug in seeded or slug in existing:
            seeded.add(slug)
            continue
        src = config.SEED_DIR / "viz" / item["file"]
        if not src.exists() or item["section"] not in sections:
            continue
        pos += 1
        file_name = f"{slug}.html"
        files.write_viz(file_name, files.prepare_html(src.read_bytes()))
        db.add(Visualization(
            slug=slug, title=item["title"], description=item.get("description", ""),
            section_id=sections[item["section"]].id, tags=item.get("tags", []),
            parts=item.get("parts", ""), file_name=file_name, position=pos, is_published=True,
        ))
        seeded.add(slug)
        added += 1
    db.commit()
    marker.write_text("\n".join(sorted(seeded)) + "\n", encoding="utf-8")
    if added:
        print(f"[seed] Добавлено стартовых визуализаций: {added}")
