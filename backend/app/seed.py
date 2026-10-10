"""Запуск: создать таблицы, синхронизировать разделы с seed/ и залить стартовые визуализации в пустую базу."""
import json

from sqlalchemy import func, select

from . import config, files
from .db import Base, SessionLocal, engine
from .models import Section, Visualization

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
            db.flush()
            db.expire(by_slug[old])
            db.delete(by_slug[old])
    db.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
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
