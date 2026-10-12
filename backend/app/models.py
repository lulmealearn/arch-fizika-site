from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # free — открыта всем; private — только тем, кому админ открыл вручную (таблица grants)
    access: Mapped[str] = mapped_column(String(10), default="free", server_default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    section: Mapped[Section] = relationship(back_populates="visualizations")


class User(Base):
    """Ученик: только ник и хеш пароля, больше ничего не храним."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(32))
    # ник в нижнем регистре: «Vasya» и «vasya» — один и тот же ученик
    nickname_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    # растёт при сбросе пароля — старые сессии ученика перестают действовать
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Homework(Base):
    """Домашнее задание: номер, название и PDF на диске storage/hw/<file_name>."""
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    file_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Lesson(Base):
    """Урок: номер, название и ссылка на запись (Телебосс, VK и т. п.)."""
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


GRANT_KINDS = ("viz", "hw", "lesson")


class Grant(Base):
    """Ручной доступ: какому ученику открыт какой материал (kind = viz / hw / lesson)."""
    __tablename__ = "grants"
    __table_args__ = (UniqueConstraint("user_id", "kind", "item_id", name="uq_grant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
