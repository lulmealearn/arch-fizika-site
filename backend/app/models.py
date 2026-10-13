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
    """Ученик (или куратор): ник и хеш пароля. Куратор — тот же аккаунт с role="curator": проверяет сданные ДЗ
    на странице /check/; tg_chat_id — куда бот присылает ему новые работы."""
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
    role: Mapped[str] = mapped_column(String(16), default="student", server_default="student")
    tg_chat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class Homework(Base):
    """Устарело: раньше ДЗ было отдельным материалом. При запуске переносится в занятия (seed._migrate_homeworks)."""
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    file_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


DEFAULT_DEADLINE_DAYS = 3  # срок на ДЗ по умолчанию, дней
DEFAULT_MOCK_DEADLINE_DAYS = 7  # срок на пробник по умолчанию, дней


class Lesson(Base):
    """Занятие — папка ученика: запись (ссылка), конспект и ДЗ (PDF в storage/hw/) и визуализации к нему."""
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    # ссылка на запись (Телебосс, VK); пустая строка — записи нет
    url: Mapped[str] = mapped_column(String(1000), default="")
    notes_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    hw_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    # раздел физики — для фильтра в кабинете; по умолчанию раздел первой визуализации в папке
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id"), nullable=True)
    # срок на ДЗ в днях с момента, когда ученик нажал «Начать»; пусто — по умолчанию (deadlines.DEFAULT_DAYS)
    deadline_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    section: Mapped[Optional[Section]] = relationship()


class LessonViz(Base):
    """Какие визуализации лежат в папке занятия (в нужном порядке)."""
    __tablename__ = "lesson_viz"
    __table_args__ = (UniqueConstraint("lesson_id", "viz_id", name="uq_lesson_viz"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    viz_id: Mapped[int] = mapped_column(ForeignKey("visualizations.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class LessonProgress(Base):
    """Срок на ДЗ занятия (deadlines.py). Нет строки или started_at пуст — «Не начато» (красная папка);
    started_at и due_at заданы — «В работе», идёт срок; submitted_at — «Сдано» (зелёная).
    Срок истёк без сдачи — занятие возвращается в «Не начато», overdue_count растёт, срок берут заново.
    done повторяет «сдано» (для сводок)."""
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    first_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    last_overdue_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Mock(Base):
    """Пробник: номер, название и вариант (HTML или PDF). Решений нет — решение владельца. Не привязан к занятиям."""
    __tablename__ = "mocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    file_name: Mapped[str] = mapped_column(String(160))
    solutions_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)  # не используется: решений у пробников нет
    # ключ первой части для автопроверки (см. mockcheck.py): [{n, answers, points, any_order}]
    answer_key: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # срок на пробник в днях с «Начать»; пусто — по умолчанию (DEFAULT_MOCK_DEADLINE_DAYS)
    deadline_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MockProgress(Base):
    """Срок на пробник — как у занятий (deadlines.py): «Не начато» → «Начать» (вариант открывается, идёт срок) →
    сдано (бланк ответов или «Сдал»). Истёк без сдачи — снова «Не начато», overdue_count +1. done повторяет «сдано»."""
    __tablename__ = "mock_progress"
    __table_args__ = (UniqueConstraint("user_id", "mock_id", name="uq_mock_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mock_id: Mapped[int] = mapped_column(ForeignKey("mocks.id", ondelete="CASCADE"), index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    first_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    last_overdue_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MockAttempt(Base):
    """Ответы ученика на первую часть пробника и результат автопроверки. Попытка одна."""
    __tablename__ = "mock_attempts"
    __table_args__ = (UniqueConstraint("user_id", "mock_id", name="uq_mock_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mock_id: Mapped[int] = mapped_column(ForeignKey("mocks.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[list] = mapped_column(JSON, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Report(Base):
    """Отчёт для родителей: личный PDF ученика с аналитикой за период. Загружает админ раз в месяц."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Visit(Base):
    """Сеанс ученика на сайте: от первого до последнего запроса; перерыв больше 30 минут — новый сеанс.
    Храним только примерное устройство (браузер и система), без IP."""
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    device: Mapped[str] = mapped_column(String(80), default="")
    hits: Mapped[int] = mapped_column(Integer, default=1)


class View(Base):
    """Что ученик открывал: запись, конспект, ДЗ, визуализацию, пробник, отчёт."""
    __tablename__ = "views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    ref: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


GRANT_KINDS = ("viz", "lesson", "mock")


class Grant(Base):
    """Ручной доступ: какому ученику открыто занятие (lesson), пробник (mock) или отдельная визуализация (viz)."""
    __tablename__ = "grants"
    __table_args__ = (UniqueConstraint("user_id", "kind", "item_id", name="uq_grant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Submission(Base):
    """Сданная работа: ДЗ занятия (lesson_id) или пробник (mock_id). Файлы ученика (фото или PDF в storage/submissions/),
    когда сдано, сколько раз до этого истекал срок, и результат проверки куратором: у ДЗ — верно из всего,
    у пробника — баллы за вторую часть (первая проверяется автоматически, MockAttempt). Файлы проверенных работ
    удаляются через SUBMISSION_KEEP_DAYS после проверки (files_purged_at), результат и комментарий остаются."""
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True, index=True)
    mock_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mocks.id", ondelete="CASCADE"), nullable=True, index=True)
    # [{"name": "файл на диске", "orig": "имя у ученика", "type": "image/jpeg" | "application/pdf", "size": байт}]
    files: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    overdue: Mapped[int] = mapped_column(Integer, default=0)  # сколько раз срок истекал до этой сдачи
    status: Mapped[str] = mapped_column(String(16), default="new")  # new — ждёт проверки, checked — проверено
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    checked_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # ник куратора или «Админ»
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_error: Mapped[str] = mapped_column(String(300), default="")
    files_purged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
