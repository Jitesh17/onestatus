"""Preset report scenarios (report-scenarios sprint).

Each preset is a deterministic ViewConfig served to the frontend, applied through the
existing POST /dashboard/apply with no LLM in the loop. The nl_phrase is the typed command
that would produce the same view, shown so managers learn the natural-language path.
Adding a scenario is one entry here. Presets with needs_team carry a "{team}" placeholder
that the frontend substitutes from the team picker before applying.
"""
from sqlalchemy.orm import Session

from . import crud

PRESETS = [
    {
        "id": "exec_summary",
        "label": "Executive summary",
        "nl_phrase": "show delivery, projects, trends and top 5 blockers",
        "needs_team": False,
        "config": {
            "sections": ["delivery", "per_project", "blockers", "trends"],
            "sort": "severity",
            "limit": 5,
            "summary": "Executive summary: delivery, projects, trends, top 5 blockers",
        },
    },
    {
        "id": "team_view",
        "label": "Team view",
        "nl_phrase": "focus on the {team} team",
        "needs_team": True,
        "config": {
            "team": "{team}",
            "sections": ["delivery", "per_person", "blockers", "next_steps"],
            "summary": "Team view for {team}",
        },
    },
    {
        "id": "my_team_week",
        "label": "My team this week",
        "nl_phrase": "show the {team} team this week",
        "needs_team": True,
        "config": {
            "team": "{team}",
            "days": 7,
            "sections": ["delivery", "activity", "blockers", "next_steps"],
            "summary": "{team} team, last 7 days",
        },
    },
    {
        "id": "blockers_review",
        "label": "Blockers review",
        "nl_phrase": "blockers and risks by severity",
        "needs_team": False,
        "config": {
            "sections": ["blockers", "risks"],
            "sort": "severity",
            "summary": "Blockers and risks, sorted by severity",
        },
    },
    {
        "id": "quarter_progress",
        "label": "Quarterly progress",
        "nl_phrase": "show trends and projects for the last 90 days",
        "needs_team": False,
        "config": {
            "days": 90,
            "sections": ["trends", "delivery", "per_project"],
            "summary": "Trends and projects, last 90 days",
        },
    },
    {
        "id": "plan_vs_actual",
        "label": "Plan vs actual",
        "nl_phrase": "show the plan view",
        "needs_team": False,
        "config": {
            "sections": ["plan", "per_project"],
            "summary": "Plan vs actual: expected progress, overdue, at-risk, stale",
        },
    },
    {
        "id": "person_workload",
        "label": "Per-person workload",
        "nl_phrase": "show workload per person",
        "needs_team": False,
        "config": {
            "sections": ["per_person", "next_steps"],
            "summary": "Workload per person",
        },
    },
]


def get_presets(db: Session) -> dict:
    """Teams come from the people table so the picker always matches the live org."""
    teams, seen = [], set()
    for p in crud.people_roster(db):
        if p.team and p.team not in seen:
            seen.add(p.team)
            teams.append(p.team)
    return {"teams": teams, "presets": PRESETS}
