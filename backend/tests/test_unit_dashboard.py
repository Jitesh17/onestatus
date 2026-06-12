"""Unit tests for crud._effective_range, crud._assignee_scope, crud.dashboard_metrics."""
import datetime as dt

from app import crud, models
from .factories import make_project, make_task, make_update, make_person, days_ago

S = models.Status
SV = models.Severity


# ---------- _effective_range ----------
def test_range_days_relative():
    start, end = crud._effective_range({"days": 7})
    assert end == dt.date.today()
    assert start == dt.date.today() - dt.timedelta(days=6)


def test_range_days_wins_over_dates():
    start, end = crud._effective_range(
        {"days": 7, "date_from": "2020-01-01", "date_to": "2020-02-01"})
    assert end == dt.date.today()
    assert start == dt.date.today() - dt.timedelta(days=6)


def test_range_bad_iso_treated_as_absent():
    assert crud._effective_range({"date_from": "junk", "date_to": "also junk"}) == (None, None)


def test_range_single_bound():
    start, end = crud._effective_range({"date_from": "2026-06-01"})
    assert start == dt.date(2026, 6, 1) and end is None


def test_range_nonpositive_days_ignored():
    start, end = crud._effective_range({"days": 0, "date_from": "2026-06-01"})
    assert start == dt.date(2026, 6, 1) and end is None
    assert crud._effective_range({"days": -3}) == (None, None)


def test_range_empty_config():
    assert crud._effective_range(None) == (None, None)
    assert crud._effective_range({}) == (None, None)


# ---------- _assignee_scope ----------
def _task_with_assignee(db, assignee):
    p = make_project(db)
    return make_task(db, p, assignee=assignee)


def test_scope_none_when_unset(db):
    assert crud._assignee_scope(db, {}) is None
    assert crud._assignee_scope(db, None) is None


def test_scope_person_case_insensitive(db):
    t = _task_with_assignee(db, "Sam")
    scope = crud._assignee_scope(db, {"person": "sam"})
    assert scope(t) is True


def test_scope_person_mismatch(db):
    t = _task_with_assignee(db, "Sam")
    assert crud._assignee_scope(db, {"person": "Casey"})(t) is False


def test_scope_unknown_team_matches_nothing(db):
    t = _task_with_assignee(db, "Sam")
    make_person(db, "Sam", team="Platform")
    assert crud._assignee_scope(db, {"team": "Ghost Team"})(t) is False


def test_scope_team_membership(db):
    make_person(db, "Sam", team="Platform")
    make_person(db, "Casey", team="Mobile")
    scope = crud._assignee_scope(db, {"team": "platform"})
    assert scope(_task_with_assignee(db, "Sam")) is True
    assert scope(_task_with_assignee(db, "Casey")) is False
    assert scope(_task_with_assignee(db, None)) is False


def test_scope_team_and_person_combined(db):
    make_person(db, "Sam", team="Platform")
    make_person(db, "Alex", team="Platform")
    scope = crud._assignee_scope(db, {"team": "Platform", "person": "Sam"})
    assert scope(_task_with_assignee(db, "Sam")) is True
    assert scope(_task_with_assignee(db, "Alex")) is False


# ---------- dashboard_metrics ----------
def test_metrics_empty_db(db):
    m = crud.dashboard_metrics(db)
    assert m["totals"] == {"projects": 0, "tasks": 0, "updates": 0}
    assert m["overall_progress"] == 0
    assert m["open_blockers"] == 0
    assert m["per_project"] == [] and m["per_team"] == [] and m["per_person"] == []
    assert m["trends"] == {"progress": [], "blockers": []}


def test_metrics_status_counts_and_mean(db):
    p = make_project(db)
    make_task(db, p, title="A", status=S.done, progress_pct=100)
    make_task(db, p, title="B", status=S.in_progress, progress_pct=50)
    make_task(db, p, title="C", status=S.blocked, progress_pct=10)
    m = crud.dashboard_metrics(db)
    assert m["task_status_counts"] == {"not_started": 0, "in_progress": 1,
                                       "blocked": 1, "done": 1}
    assert m["overall_progress"] == 53  # round(160/3)


def test_metrics_project_filter(db):
    p1, p2 = make_project(db, "P1"), make_project(db, "P2")
    make_task(db, p1, title="A")
    make_task(db, p2, title="B")
    m = crud.dashboard_metrics(db, {"project": "P1"})
    assert m["totals"] == {"projects": 1, "tasks": 1, "updates": 0}
    assert [r["name"] for r in m["per_project"]] == ["P1"]


def test_metrics_status_filter(db):
    p = make_project(db)
    make_task(db, p, title="A", status=S.blocked)
    make_task(db, p, title="B", status=S.done)
    m = crud.dashboard_metrics(db, {"status": "blocked"})
    assert m["totals"]["tasks"] == 1
    assert m["per_project"][0]["task_count"] == 1


def test_metrics_severity_filter(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[("High one", SV.high), ("Low one", SV.low)])
    m = crud.dashboard_metrics(db, {"severity": "high"})
    assert m["open_blockers"] == 1
    assert m["blockers_list"][0]["description"] == "High one"
    assert m["open_blockers_by_severity"] == {"low": 0, "medium": 0, "high": 1}


def test_metrics_resolved_blockers_excluded(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[("Open one", SV.medium, None, "open"),
                                 ("Fixed one", SV.medium, None, "resolved")])
    m = crud.dashboard_metrics(db)
    assert m["open_blockers"] == 1
    assert m["blockers_list"][0]["description"] == "Open one"


def test_metrics_blockers_sorted_by_severity(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[("low", SV.low), ("high", SV.high), ("med", SV.medium)])
    m = crud.dashboard_metrics(db)
    assert [b["severity"] for b in m["blockers_list"]] == ["high", "medium", "low"]


def test_metrics_next_steps_sorted_by_due_date_nulls_last(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, next_steps=[("no date", None, None),
                                   ("later", None, dt.date(2026, 7, 1)),
                                   ("sooner", None, dt.date(2026, 6, 15))])
    m = crud.dashboard_metrics(db)
    assert [s["description"] for s in m["upcoming_next_steps"]] == ["sooner", "later", "no date"]


def test_metrics_team_filter_prunes_projects(db):
    make_person(db, "Sam", team="Platform")
    make_person(db, "Casey", team="Mobile")
    p1, p2 = make_project(db, "P1"), make_project(db, "P2")
    make_task(db, p1, title="A", assignee="Sam")
    make_task(db, p2, title="B", assignee="Casey")
    m = crud.dashboard_metrics(db, {"team": "Mobile"})
    assert m["totals"] == {"projects": 1, "tasks": 1, "updates": 0}
    assert [r["name"] for r in m["per_project"]] == ["P2"]


def test_metrics_per_team_rollup(db):
    make_person(db, "Sam", team="Platform", department="Engineering")
    make_person(db, "Alex", team="Platform", department="Engineering")
    make_person(db, "Casey", team="Mobile", department="Engineering")
    p = make_project(db)
    t1 = make_task(db, p, title="A", assignee="Sam", status=S.done, progress_pct=100)
    make_task(db, p, title="B", assignee="Alex", status=S.in_progress, progress_pct=40)
    make_task(db, p, title="C", assignee="Casey", progress_pct=10)
    make_update(db, t1, blockers=[("stuck", SV.high)])
    m = crud.dashboard_metrics(db)
    teams = {r["team"]: r for r in m["per_team"]}
    ds = teams["Platform"]
    assert ds["department"] == "Engineering"
    assert sorted(ds["members"]) == ["Alex", "Sam"]
    assert ds["task_count"] == 2 and ds["done_task_count"] == 1
    assert ds["avg_progress"] == 70 and ds["open_blocker_count"] == 1
    assert teams["Mobile"]["task_count"] == 1


def test_metrics_team_focus_narrows_team_rows(db):
    make_person(db, "Sam", team="Platform")
    make_person(db, "Casey", team="Mobile")
    m = crud.dashboard_metrics(db, {"team": "Platform"})
    assert [r["team"] for r in m["per_team"]] == ["Platform"]
    assert [r["name"] for r in m["per_person"]] == ["Sam"]


def test_metrics_per_person_includes_idle_roster_member(db):
    make_person(db, "Suzuki-san", team="Product Ops")
    m = crud.dashboard_metrics(db)
    row = m["per_person"][0]
    assert row["name"] == "Suzuki-san" and row["task_count"] == 0
    assert row["avg_progress"] == 0 and row["next_step_count"] == 0


def test_metrics_per_person_unknown_assignee_gets_teamless_row(db):
    p = make_project(db)
    make_task(db, p, assignee="Contractor X")
    m = crud.dashboard_metrics(db)
    row = next(r for r in m["per_person"] if r["name"] == "Contractor X")
    assert row["team"] is None and row["task_count"] == 1


def test_metrics_per_person_blocker_dedup_and_next_steps(db):
    make_person(db, "Sam", team="Platform")
    p = make_project(db)
    t = make_task(db, p, assignee="Sam")
    # Same blocker visible via Sam's own task AND owned by Sam: counts once.
    make_update(db, t, blockers=[("stuck", SV.high, "Sam")],
                next_steps=[("do thing", "Sam", None), ("other", "Casey", None)])
    m = crud.dashboard_metrics(db)
    row = next(r for r in m["per_person"] if r["name"] == "Sam")
    assert row["open_blocker_count"] == 1
    assert row["next_step_count"] == 1


def test_metrics_per_person_sorted_by_task_count(db):
    make_person(db, "Idle", team="T")
    make_person(db, "Busy", team="T")
    p = make_project(db)
    make_task(db, p, title="A", assignee="Busy")
    make_task(db, p, title="B", assignee="Busy")
    m = crud.dashboard_metrics(db)
    assert [r["name"] for r in m["per_person"]] == ["Busy", "Idle"]


def test_metrics_sort_progress_reorders_projects(db):
    p1, p2 = make_project(db, "Low"), make_project(db, "High")
    make_task(db, p1, progress_pct=10)
    make_task(db, p2, progress_pct=90)
    m = crud.dashboard_metrics(db, {"sort": "progress"})
    assert [r["name"] for r in m["per_project"]] == ["High", "Low"]


def test_metrics_limit_caps_lists(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[(f"b{i}", SV.medium) for i in range(5)],
                next_steps=[(f"s{i}", None, None) for i in range(5)])
    m = crud.dashboard_metrics(db, {"limit": 2})
    assert len(m["blockers_list"]) == 2 and len(m["upcoming_next_steps"]) == 2
    assert m["open_blockers"] == 5  # the count stays whole; only the list is capped


def test_metrics_recent_default_cap(db):
    p = make_project(db)
    t = make_task(db, p)
    for i in range(crud.RECENT_LIMIT + 3):
        make_update(db, t, raw_text=f"update {i}")
    m = crud.dashboard_metrics(db)
    assert len(m["recent_updates"]) == crud.RECENT_LIMIT
    assert m["totals"]["updates"] == crud.RECENT_LIMIT + 3


def test_metrics_nonpositive_limit_ignored(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[(f"b{i}", SV.medium) for i in range(3)])
    m = crud.dashboard_metrics(db, {"limit": 0})
    assert len(m["blockers_list"]) == 3


def test_metrics_date_range_scopes_events_not_state(db):
    p = make_project(db)
    t = make_task(db, p, progress_pct=60)
    make_update(db, t, created_at=days_ago(30), blockers=[("old", SV.high)])
    make_update(db, t, created_at=days_ago(1), blockers=[("new", SV.high)])
    m = crud.dashboard_metrics(db, {"days": 7})
    assert m["totals"]["updates"] == 1
    assert [b["description"] for b in m["blockers_list"]] == ["new"]
    # State stays whole-world: tasks and progress are unchanged by the window.
    assert m["totals"]["tasks"] == 1 and m["overall_progress"] == 60
