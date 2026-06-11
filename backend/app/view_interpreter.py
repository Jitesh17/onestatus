"""Natural-language dashboard reconfiguration (week 6).

Turns a short command ("only blocked tasks in BRAVIA", "hide risks, top 3 blockers by
severity") into a validated ViewConfig dict that crud.dashboard_metrics applies. Reuses
the same local LLM (Ollama JSON mode) as the extractor, grounded in the known projects.
"""
from .extractor import ollama_json, ExtractorError  # noqa: F401  (re-export for callers)

SECTIONS = ["delivery", "per_project", "blockers", "risks", "activity", "next_steps"]
STATUSES = ["not_started", "in_progress", "blocked", "done"]
SEVERITIES = ["low", "medium", "high"]
SORTS = ["severity", "recent", "progress", "due"]

EMPTY_CONFIG = {
    "project": None, "status": None, "severity": None,
    "sections": [], "hide": [], "sort": None, "limit": None, "summary": "",
}


def _system_prompt(world):
    projects = "\n".join(
        f"- {p['name']}" + (f" (JA: {p['name_ja']})" if p.get("name_ja") else "")
        for p in world.get("projects", [])
    )
    return f"""You convert a manager's request into a strict JSON dashboard view-config.

Known projects:
{projects}

Sections: delivery (status chart), per_project (project table), blockers, risks,
activity (recent updates), next_steps.

Return JSON with exactly these keys:
- "project": the FULL known project name the request focuses on, or null for all. Match abbreviations
  to the full name (e.g. "BRAVIA" or "bravia" -> "BRAVIA Panel Calibration").
- "status": one of {STATUSES} when the request focuses on a task status, else null.
  "blocked tasks"->"blocked"; "in progress"/"ongoing"->"in_progress"; "finished"/"completed"->"done"; "not started"->"not_started".
- "severity": one of {SEVERITIES} ONLY when the request names a blocker severity LEVEL
  ("high severity blockers", "critical", "low priority"). The phrases "by severity" / "sort by severity"
  / "most severe" are SORTING, not a filter -> leave severity null and set "sort":"severity".
- "sections": sections to SHOW ONLY (subset above). Use ["blockers"] for "just blockers". Leave [] when
  the request only filters (project/status/severity) or only sorts -- e.g. "focus on Xperia" -> sections [].
- "hide": sections to REMOVE. "hide risks" -> ["risks"]. "drop the project table" -> ["per_project"]. Else [].
- "sort": one of {SORTS} or null. "by severity"/"most severe"->"severity"; "newest"/"latest"->"recent";
  "by progress"->"progress"; "by due date"->"due".
- "limit": integer cap for lists ("top 3"->3), or null.
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


def _coerce(raw, world):
    out = dict(EMPTY_CONFIG)
    out["project"] = _match_project(raw.get("project"), world)
    out["status"] = raw.get("status") if raw.get("status") in STATUSES else None
    out["severity"] = raw.get("severity") if raw.get("severity") in SEVERITIES else None
    out["sections"] = [s for s in (raw.get("sections") or []) if s in SECTIONS]
    out["hide"] = [s for s in (raw.get("hide") or []) if s in SECTIONS]
    out["sort"] = raw.get("sort") if raw.get("sort") in SORTS else None

    lim = raw.get("limit")
    out["limit"] = int(lim) if isinstance(lim, (int, float)) and lim > 0 else None
    out["summary"] = (raw.get("summary") or "").strip()
    return out


def interpret_view(request, world, model=None):
    """Interpret a NL request into a validated ViewConfig dict. Empty config = full view."""
    if not request or not request.strip():
        return dict(EMPTY_CONFIG)
    raw = ollama_json(_system_prompt(world), request, model=model)
    return _coerce(raw, world)
