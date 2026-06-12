"""ORM models for the Sony OneStatus data model.

These are the canonical entities the rest of the system reads and writes.
Week 1 covers manual entry, so every field here is set by a human via the UI.
The AI in later weeks will populate the same tables, never new ones.
"""
import datetime as dt
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .database import Base


class Status(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_ja: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[Status] = mapped_column(SAEnum(Status), default=Status.in_progress)
    start_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    target_date: Mapped[dt.date | None] = mapped_column(nullable=True)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(300))
    title_ja: Mapped[str | None] = mapped_column(String(300), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[Status] = mapped_column(SAEnum(Status), default=Status.not_started)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[dt.date | None] = mapped_column(nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    updates: Mapped[list["Update"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Update(Base):
    __tablename__ = "updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en")  # en or ja
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="text")  # text or voice
    confirmed: Mapped[bool] = mapped_column(default=True)  # week 1: manual entry is confirmed by definition
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    # Snapshot of what this update reported (trends sprint). Nullable: older rows and
    # updates that don't mention status/progress leave them empty. Current state lives on Task.
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="updates")
    blockers: Mapped[list["Blocker"]] = relationship(back_populates="update", cascade="all, delete-orphan")
    risks: Mapped[list["Risk"]] = relationship(back_populates="update", cascade="all, delete-orphan")
    next_steps: Mapped[list["NextStep"]] = relationship(back_populates="update", cascade="all, delete-orphan")


class Blocker(Base):
    __tablename__ = "blockers"
    id: Mapped[int] = mapped_column(primary_key=True)
    update_id: Mapped[int] = mapped_column(ForeignKey("updates.id"))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity), default=Severity.medium)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open or resolved

    update: Mapped["Update"] = relationship(back_populates="blockers")


class Risk(Base):
    __tablename__ = "risks"
    id: Mapped[int] = mapped_column(primary_key=True)
    update_id: Mapped[int] = mapped_column(ForeignKey("updates.id"))
    description: Mapped[str] = mapped_column(Text)
    likelihood: Mapped[str | None] = mapped_column(String(20), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)

    update: Mapped["Update"] = relationship(back_populates="risks")


class NextStep(Base):
    __tablename__ = "next_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    update_id: Mapped[int] = mapped_column(ForeignKey("updates.id"))
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(nullable=True)

    update: Mapped["Update"] = relationship(back_populates="next_steps")


class Person(Base):
    """Org roster (report-scenarios sprint). Team/department live flat on the person;
    assignee/author/owner stay free text on the records and are matched by name at
    aggregation time, so a person changing teams never rewrites history.
    """
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    name_ja: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)


class SavedView(Base):
    """A named dashboard view-config (week 6). `config` holds the ViewConfig JSON as text."""
    __tablename__ = "saved_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[str] = mapped_column(Text)  # JSON-encoded ViewConfig
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class AppSetting(Base):
    """Single-row store for runtime settings chosen in the UI (id is always 1).

    `data` holds the non-secret mutable settings as JSON; the LLM API key is
    deliberately excluded (env-or-memory only). New table, so create_all covers
    it and migrate.py needs no entry.
    """
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[str] = mapped_column(Text, default="{}")
