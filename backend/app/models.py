from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Section(Base):
    """Раздел физики: цвет язычка папки и тега."""
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(16))
    tint: Mapped[str] = mapped_column(String(16))
    ink: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer, default=0)

    visualizations: Mapped[List["Visualization"]] = relationship(back_populates="section")


class Visualization(Base):
    """Метаданные визуализации. Сам HTML лежит на диске: storage/viz/<file_name>."""
    __tablename__ = "visualizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    parts: Mapped[str] = mapped_column(String(60), default="")
    file_name: Mapped[str] = mapped_column(String(120))
    cover_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    section: Mapped[Section] = relationship(back_populates="visualizations")
