"""Pydantic schemas: the validated shapes for API input and output.

These mirror the ORM models but keep the API contract separate from storage,
so we can change one without breaking the other.
"""
import datetime as dt
from pydantic import BaseModel, Field, ConfigDict
from .models import Status, Severity


# ---------- Project ----------
class ProjectBase(BaseModel):
    name: str
    name_ja: str | None = None
    owner: str | None = None
    status: Status = Status.in_progress
    start_date: dt.date | None = None
    target_date: dt.date | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Task ----------
class TaskBase(BaseModel):
    project_id: int
    title: str
    title_ja: str | None = None
    assignee: str | None = None
    status: Status = Status.not_started
    progress_pct: int = Field(default=0, ge=0, le=100)
    due_date: dt.date | None = None


class TaskCreate(TaskBase):
    pass


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Nested items on an update ----------
class BlockerIn(BaseModel):
    description: str
    severity: Severity = Severity.medium
    owner: str | None = None
    status: str = "open"


class RiskIn(BaseModel):
    description: str
    likelihood: str | None = None
    impact: str | None = None
    mitigation: str | None = None
    owner: str | None = None


class NextStepIn(BaseModel):
    description: str
    owner: str | None = None
    due_date: dt.date | None = None


# ---------- Update ----------
class UpdateCreate(BaseModel):
    task_id: int | None = None
    author: str | None = None
    language: str = "en"
    raw_text: str | None = None
    source: str = "text"
    blockers: list[BlockerIn] = []
    risks: list[RiskIn] = []
    next_steps: list[NextStepIn] = []


class BlockerOut(BlockerIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RiskOut(RiskIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class NextStepOut(NextStepIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class UpdateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int | None
    author: str | None
    language: str
    raw_text: str | None
    source: str
    confirmed: bool
    created_at: dt.datetime
    blockers: list[BlockerOut] = []
    risks: list[RiskOut] = []
    next_steps: list[NextStepOut] = []


# ---------- Extraction (week 2): text -> structured draft, nothing persisted ----------
# Draft-nested types are deliberately LENIENT: the model may leave severity unset or emit a
# vague due_date ("Friday", "金曜日"). The human resolves these in the editor before the strict
# BlockerIn / NextStepIn validate on the POST /updates save.
class BlockerDraft(BaseModel):
    description: str
    severity: Severity | None = None
    owner: str | None = None
    status: str = "open"


class NextStepDraft(BaseModel):
    description: str
    owner: str | None = None
    due_date: str | None = None  # free text; may be ISO, "Friday", or "金曜日"


class ExtractRequest(BaseModel):
    raw_text: str
    language: str = "en"
    model: str | None = None  # override the default local model; None uses the server default


class ExtractDraft(BaseModel):
    """The model's proposal, shown in the confirmation editor before saving.

    Richer than what `/updates` persists: `project`/`task` are matched names (with a
    resolved `task_id` or null), and `progress_pct`/`status`/`period`/`owners` are
    surfaced for the human even though some live on Task, not Update.
    """
    project: str = "unknown"            # known project name or "unknown"
    task: str | None = None             # known task title or null
    task_id: int | None = None          # resolved against the live DB, null if unmatched
    unknown_project: bool = False
    unknown_task: bool = False
    status: Status | None = None
    progress_pct: int | None = None
    blockers: list[BlockerDraft] = []
    risks: list[RiskIn] = []
    next_steps: list[NextStepDraft] = []
    owners: list[str] = []
    period: str | None = None
    confidence: float = 0.0
