"""Natural-language dashboard reconfiguration (week 6).

Turns a short command ("only blocked tasks in Website Redesign", "hide risks, top 3 blockers by
severity") into a validated ViewConfig dict that crud.dashboard_metrics applies. Reuses
the same local LLM (Ollama JSON mode) as the extractor, grounded in the known projects.
"""
import datetime as dt
import re

from .extractor import ollama_json, ExtractorError  # noqa: F401  (re-export for callers)

SECTIONS = ["delivery", "per_project", "per_team", "per_person",
            "blockers", "risks", "activity", "next_steps", "trends"]
STATUSES = ["not_started", "in_progress", "blocked", "done"]
SEVERITIES = ["low", "medium", "high"]
SORTS = ["severity", "recent", "progress", "due"]

EMPTY_CONFIG = {
    "project": None, "status": None, "severity": None, "team": None, "person": None,
    "sections": [], "hide": [], "sort": None, "limit": None,
    "days": None, "date_from": None, "date_to": None, "summary": "",
}


def _system_prompt(world):
    projects = "\n".join(
        f"- {p['name']}" + (f" (JA: {p['name_ja']})" if p.get("name_ja") else "")
        for p in world.get("projects", [])
    )
    teams = "\n".join(
        f"- {t['name']} (members: {', '.join(t['members'])})"
        for t in world.get("teams", [])
    ) or "- (none)"
    people = ", ".join(world.get("people", []))
    today = dt.date.today().isoformat()
    return f"""You convert a manager's request into a strict JSON dashboard view-config.
Today's date is {today}.

Known projects:
{projects}

Known teams:
{teams}

Known people: {people}

Sections: delivery (status chart), per_project (project table), per_team (team rollup table),
per_person (people workload table), blockers, risks, activity (recent updates), next_steps,
trends (charts over time).

Return JSON with exactly these keys:
- "project": the FULL known project name the request focuses on, or null for all. Match abbreviations
  to the full name (e.g. "redesign" or "the website project" -> "Website Redesign").
- "team": the FULL known team name ONLY when the request asks about that team's work
  ("the Mobile team", "Platform status"). Else null. Never guess a team for "my team".
- "person": the FULL known person name ONLY when the request asks about one person's tasks or
  workload ("Sam's tasks" -> "Sam"; "what is Casey working on" -> "Casey"). A possessive
  name always sets person. A person mentioned as a blocker owner or in passing is NOT a focus.
  Else null.
- "status": one of {STATUSES} when the request focuses on a task status, else null.
  "blocked tasks"->"blocked"; "in progress"/"ongoing"->"in_progress"; "finished"/"completed"->"done"; "not started"->"not_started".
- "severity": one of {SEVERITIES} ONLY when the request EXPLICITLY contains a severity-level word
  ("high severity blockers", "critical", "low priority"). The phrases "by severity" / "sort by severity"
  / "most severe" / "top blockers" are SORTING, not a filter -> leave severity null and set "sort":"severity".
- "sections": sections to SHOW ONLY (subset above). Use ["blockers"] for "just blockers";
  "workload per person" / "per person" -> ["per_person"]; "by team" / "team breakdown" -> ["per_team"].
  Leave [] when the request only filters (project/status/severity/team/person) or only sorts --
  "focus on Mobile App v2" -> sections []; "focus on the Platform team" -> team set, sections [].
  NEVER narrow sections unless the user names which section(s) they want to see.
- "hide": sections to REMOVE. "hide risks" -> ["risks"]. "drop the project table" -> ["per_project"]. Else [].
- "sort": one of {SORTS} or null. "by severity"/"most severe"->"severity"; "newest"/"latest"->"recent";
  "by progress"->"progress"; "by due date"->"due".
- "limit": integer cap for lists ("top 3"->3), or null.
- "days": integer lookback ONLY when the request names a relative time window: "last 2 weeks"->14,
  "this week"->7, "last month"->30, "recent"/"recently"->7. A Japanese relative time word maps the
  same way (this week->7, last week->7, last month->30). Else null.
- "date_from"/"date_to": ISO dates (YYYY-MM-DD) ONLY for explicit calendar bounds ("since June 1"->
  date_from "{dt.date.today().year}-06-01"; "until Friday"-> the ISO date). Else null. When the
  request is relative, prefer "days" and leave these null.
- "summary": a short plain-English echo of what you applied.

Set only what the request implies; otherwise null or []. Return ONLY the JSON object."""


def _match_project(value, world):
    """Map a possibly-abbreviated project name to a known full name, or None."""
    if not value:
        return None
    names = [p["name"] for p in world.get("projects", [])]
    if value in names:
        return value
    low = value.strip().lower()
    for n in names:
        if n.lower() == low or low in n.lower() or n.lower() in low:
            return n
    return None


def _match_team(value, world):
    """Map a possibly-partial team name to a known team name, or None."""
    if not value:
        return None
    names = [t["name"] for t in world.get("teams", [])]
    if value in names:
        return value
    low = str(value).strip().lower()
    for n in names:
        if n.lower() == low or low in n.lower() or n.lower() in low:
            return n
    return None


def _match_person(value, world):
    """Map a name (possibly missing an honorific, e.g. "yamada") to a known person, or None."""
    if not value:
        return None
    names = world.get("people", [])
    if value in names:
        return value
    low = str(value).strip().lower()
    for n in names:
        if n.lower() == low or n.split("-")[0].lower() == low:
            return n
    return None


# Words that justify a TEAM filter. Same guard pattern as severity below: the 7B model
# sometimes invents a team focus ("how are things" -> first team in the list). Keep the
# team only when the request names the team or at least talks about a team.
_TEAM_WORDS = ("team", "squad", "チーム", "班")


def _explicit_team(request, team):
    t = (request or "").lower()
    return (team or "").lower() in t or any(w in t for w in _TEAM_WORDS)


def _explicit_person(request, person):
    """The matched person's base token must literally appear ("yamada" matches "Yamada-san")."""
    t = (request or "").lower()
    return bool(person) and person.split("-")[0].lower() in t


# Words that justify keeping a SECTION in the show-only list. Same guard pattern as
# severity/time below: despite the prompt, the 7B model sometimes narrows sections on its
# own ("how are things" -> a guessed subset), which silently hides KPIs. A section survives
# only when the request literally contains a word for it.
_SECTION_WORDS = {
    "delivery": ("delivery", "kpi"),
    "per_project": ("project", "プロジェクト"),
    "per_team": ("team", "squad", "チーム", "班"),
    "per_person": ("person", "people", "workload", "everyone", "担当"),
    "blockers": ("blocker", "ブロッカー", "障害"),
    "risks": ("risk", "リスク"),
    "activity": ("activity", "update", "recent", "latest", "活動", "更新"),
    "next_steps": ("next step", "next-step", "action item", "todo", "次"),
    "trends": ("trend", "chart", "graph", "history", "over time", "トレンド", "推移"),
}


def _explicit_sections(sections, request):
    t = (request or "").lower()
    return [s for s in sections if any(w in t for w in _SECTION_WORDS.get(s, ()))]


# Words that justify a severity FILTER. Deliberately narrow: "by severity" / "most
# severe" are sorting phrases and must not pass. JA terms kept specific ("中" alone
# would false-match 進行中).
_SEVERITY_WORDS = ("high", "medium", "low", "critical", "urgent", "重大", "緊急", "高い", "低い", "深刻")


def _explicit_severity(request):
    t = (request or "").lower()
    return any(w in t for w in _SEVERITY_WORDS)


# Words that justify DATE fields. Same guard pattern as severity: 7B sometimes invents a
# range ("how are things" -> days 7); drop date fields unless the request talks about time.
_TIME_WORDS = ("week", "day", "month", "since", "last", "recent", "today", "yesterday",
               "until", "till", "from", "今週", "先週", "今月", "先月", "最近", "今日", "昨日", "から", "まで")

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _explicit_time(request):
    t = (request or "").lower()
    return any(w in t for w in _TIME_WORDS)


def _iso_or_none(value):
    s = str(value).strip()[:10] if value else ""
    return s if _ISO_RE.match(s) else None


def _coerce(raw, world, request=""):
    out = dict(EMPTY_CONFIG)
    out["project"] = _match_project(raw.get("project"), world)
    out["status"] = raw.get("status") if raw.get("status") in STATUSES else None
    out["severity"] = raw.get("severity") if raw.get("severity") in SEVERITIES else None
    out["sections"] = _explicit_sections(
        [s for s in (raw.get("sections") or []) if s in SECTIONS], request)
    out["hide"] = [s for s in (raw.get("hide") or []) if s in SECTIONS]
    out["sort"] = raw.get("sort") if raw.get("sort") in SORTS else None
    # 7B guard: "top 3 blockers by severity" must sort, not filter. Despite the
    # prompt, the model sometimes also sets severity="high"; drop the filter unless
    # the request literally contains a severity-level word.
    if out["severity"] and not _explicit_severity(request):
        out["severity"] = None

    # Team/person follow the same guard pattern: resolve against the known org, then drop
    # the filter unless the request literally backs it up.
    out["team"] = _match_team(raw.get("team"), world)
    if out["team"] and not _explicit_team(request, out["team"]):
        out["team"] = None
    out["person"] = _match_person(raw.get("person"), world)
    if out["person"] and not _explicit_person(request, out["person"]):
        out["person"] = None

    lim = raw.get("limit")
    out["limit"] = int(lim) if isinstance(lim, (int, float)) and lim > 0 else None

    days = raw.get("days")
    out["days"] = int(days) if isinstance(days, (int, float)) and days > 0 else None
    out["date_from"] = _iso_or_none(raw.get("date_from"))
    out["date_to"] = _iso_or_none(raw.get("date_to"))
    # Same 7B guard as severity: no date scoping unless the request literally mentions time.
    if not _explicit_time(request):
        out["days"] = out["date_from"] = out["date_to"] = None
    if out["days"]:
        out["date_from"] = out["date_to"] = None  # days wins; keep the config unambiguous

    out["summary"] = (raw.get("summary") or "").strip()
    return out


def interpret_view(request, world, model=None):
    """Interpret a NL request into a validated ViewConfig dict. Empty config = full view."""
    if not request or not request.strip():
        return dict(EMPTY_CONFIG)
    raw = ollama_json(_system_prompt(world), request, model=model)
    return _coerce(raw, world, request=request)
