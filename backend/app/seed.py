"""Первый запуск: создать таблицы и залить разделы и стартовые визуализации из папки seed/."""
import json

from sqlalchemy import func, select

from . import config, files
from .db import Base, SessionLocal, engine
from .models import Section, Visualization


def init_db() -> None:
    Base.metadata.create_all(engine)
    seed_file = config.SEED_DIR / "visualizations.json"
    if not seed_file.exists():
        return
    data = json.loads(seed_file.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        if db.scalar(select(func.count(Section.id))) == 0:
            for i, s in enumerate(data.get("sections", [])):
                db.add(Section(slug=s["id"], label=s["label"], color=s["color"], tint=s["tint"], ink=s["ink"], position=i))
            db.commit()

        if db.scalar(select(func.count(Visualization.id))) == 0:
            sections = {s.slug: s for s in db.scalars(select(Section))}
            for i, item in enumerate(data.get("items", [])):
                src = config.SEED_DIR / "viz" / item["file"]
                if not src.exists() or item["section"] not in sections:
                    continue
                slug = item["id"]
                file_name = f"{slug}.html"
                files.write_viz(file_name, files.prepare_html(src.read_bytes()))
                db.add(Visualization(
                    slug=slug, title=item["title"], description=item.get("description", ""),
                    section_id=sections[item["section"]].id, tags=item.get("tags", []),
                    parts=item.get("parts", ""), file_name=file_name, position=i, is_published=True,
                ))
            db.commit()
            print(f"[seed] Импортировано визуализаций: {db.scalar(select(func.count(Visualization.id)))}")
