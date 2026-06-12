"""Pydantic schemas: the validated shapes for API input and output.

These mirror the ORM models but keep the API contract separate from storage,
so we can change one without breaking the other.
"""
import datetime as dt
import os
from typing import Literal

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


# Cap on free-text bodies that reach storage or the local LLM. Real updates are a few
# sentences; this only stops megabyte-scale payloads, not anything a person types.
# Env-overridable; binds into the Field validators at import, so boot-time only.
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "10000"))


# ---------- Update ----------
class UpdateCreate(BaseModel):
    task_id: int | None = None
    author: str | None = None
    language: str = "en"
    raw_text: str | None = Field(default=None, max_length=MAX_TEXT_LEN)
    source: str = "text"
    status: Status | None = None                              # snapshot; also patches the Task
    progress_pct: int | None = Field(default=None, ge=0, le=100)
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
    status: str | None = None
    progress_pct: int | None = None
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


class TranscriptOut(BaseModel):
    """Result of POST /transcribe (week 4). The text feeds the existing extract flow."""
    text: str
    language: str
    duration: float


class ExtractRequest(BaseModel):
    raw_text: str = Field(max_length=MAX_TEXT_LEN)
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


# ---------- Dashboard (week 5): fixed manager KPIs, read-only ----------
class TaskStatusCounts(BaseModel):
    not_started: int = 0
    in_progress: int = 0
    blocked: int = 0
    done: int = 0


class SeverityCounts(BaseModel):
    low: int = 0
    medium: int = 0
    high: int = 0


class BlockerRow(BaseModel):
    description: str
    severity: str
    owner: str | None = None
    task: str | None = None
    project: str | None = None


class RiskRow(BaseModel):
    description: str
    impact: str | None = None
    mitigation: str | None = None
    owner: str | None = None
    task: str | None = None
    project: str | None = None


class NextStepRow(BaseModel):
    description: str
    owner: str | None = None
    due_date: str | None = None
    task: str | None = None
    project: str | None = None


class RecentUpdateRow(BaseModel):
    id: int
    task: str | None = None
    project: str | None = None
    author: str | None = None
    language: str
    source: str
    created_at: dt.datetime
    snippet: str
    blocker_count: int
    risk_count: int
    next_step_count: int


class ProjectRollupRow(BaseModel):
    id: int
    name: str
    name_ja: str | None = None
    status: str
    owner: str | None = None
    task_count: int
    avg_progress: int
    open_blocker_count: int
    done_task_count: int


class TeamRollupRow(BaseModel):
    team: str
    department: str | None = None
    members: list[str] = []
    task_count: int
    done_task_count: int
    avg_progress: int
    open_blocker_count: int


class PersonRollupRow(BaseModel):
    name: str
    team: str | None = None               # null for assignees missing from the roster
    task_count: int
    done_task_count: int
    avg_progress: int
    open_blocker_count: int
    next_step_count: int                  # owner-matched: the workload signal


class TrendPoint(BaseModel):
    date: str                             # ISO day
    value: int


class Trends(BaseModel):
    progress: list[TrendPoint] = []       # mean task progress per day (carry-forward)
    blockers: list[TrendPoint] = []       # open blocker count per day (opens − resolves)


class DashboardOut(BaseModel):
    totals: dict[str, int]
    task_status_counts: TaskStatusCounts
    overall_progress: int
    open_blockers: int
    open_blockers_by_severity: SeverityCounts
    open_risks: int
    blockers_list: list[BlockerRow] = []
    risks_list: list[RiskRow] = []
    recent_updates: list[RecentUpdateRow] = []
    upcoming_next_steps: list[NextStepRow] = []
    per_project: list[ProjectRollupRow] = []
    per_team: list[TeamRollupRow] = []
    per_person: list[PersonRollupRow] = []
    trends: Trends = Trends()


# ---------- NL dashboard reconfiguration + saved views (week 6) ----------
class ViewConfig(BaseModel):
    project: str | None = None
    status: str | None = None
    severity: str | None = None
    team: str | None = None           # roster team name; scopes tasks by member assignees
    person: str | None = None         # roster (or free-text) name; scopes tasks by assignee
    sections: list[str] = []          # [] = all; else show only these
    hide: list[str] = []              # sections to remove (subtractive intent, e.g. "hide risks")
    sort: str | None = None           # severity | recent | progress | due
    limit: int | None = None
    days: int | None = None           # relative lookback ("last 2 weeks" -> 14); wins over dates
    date_from: str | None = None      # ISO day, inclusive
    date_to: str | None = None        # ISO day, inclusive
    summary: str = ""                 # human echo of what was understood


class ConfigureRequest(BaseModel):
    request: str = Field(max_length=MAX_TEXT_LEN)
    language: str = "en"
    model: str | None = None


class ApplyRequest(BaseModel):
    config: ViewConfig


class ConfiguredDashboard(BaseModel):
    config: ViewConfig
    dashboard: DashboardOut


class PresetOut(BaseModel):
    """A selectable report scenario: a deterministic ViewConfig plus the NL phrase that
    would produce it, so managers learn the typed path while clicking chips."""
    id: str
    label: str
    nl_phrase: str
    config: ViewConfig
    needs_team: bool = False          # config contains a {team} placeholder to substitute


class PresetsOut(BaseModel):
    teams: list[str] = []
    presets: list[PresetOut] = []


class SavedViewIn(BaseModel):
    name: str
    config: ViewConfig


class SavedViewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    config: ViewConfig
    created_at: dt.datetime


# ---------- Runtime settings (provider/model configuration) ----------
class SettingsOut(BaseModel):
    """Effective runtime settings. The API key itself is never returned;
    api_key_set tells the UI whether one is loaded."""
    llm_provider: str
    ollama_url: str
    llm_model: str
    llm_base_url: str
    llm_temperature: float
    llm_timeout: int
    api_key_set: bool
    whisper_model: str
    whisper_device: str
    whisper_compute: str
    whisper_beam: int
    whisper_vad: bool


class SettingsUpdate(BaseModel):
    """Partial update; only the fields present are changed. Literal types make
    an invalid provider or device a 422 before anything is applied."""
    llm_provider: Literal["ollama", "openai", "anthropic"] | None = None
    ollama_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None      # write-only; never echoed back
    llm_base_url: str | None = None
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    llm_timeout: int | None = Field(default=None, ge=1, le=600)
    whisper_model: Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"] | None = None
    whisper_device: Literal["cpu", "cuda"] | None = None
    whisper_compute: str | None = None
    whisper_beam: int | None = Field(default=None, ge=1, le=10)
    whisper_vad: bool | None = None


class ModelsOut(BaseModel):
    """What the settings panel can offer: installed Ollama models plus the
    fixed whisper size list. `warning` is set when Ollama is unreachable."""
    ollama_models: list[str] = []
    whisper_sizes: list[str] = []
    warning: str | None = None


# ---------- Auth (auth sprint) ----------
# bcrypt hashes at most 72 BYTES; the schema cap keeps longer passwords from being
# silently truncated. max_length counts characters, so multibyte input is re-checked
# in the router before hashing.
PASSWORD_MAX = 72


class LoginIn(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=PASSWORD_MAX)


class MeOut(BaseModel):
    """The logged-in identity the SPA gates on. `author` is the display name the
    server will write on this user's updates (linked person, else username)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    person_id: int | None = None
    author: str


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=8, max_length=PASSWORD_MAX)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=PASSWORD_MAX)
    role: Literal["member", "manager", "admin"] = "member"
    person_id: int | None = None


class UserUpdate(BaseModel):
    """Partial admin update; only the fields present are changed."""
    role: Literal["member", "manager", "admin"] | None = None
    person_id: int | None = None
    is_active: bool | None = None
    clear_person: bool = False          # person_id=None means "leave alone", so unlinking is explicit


class UserPasswordSet(BaseModel):
    new_password: str = Field(min_length=8, max_length=PASSWORD_MAX)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    person_id: int | None = None
    is_active: bool
    created_at: dt.datetime
