"""Unit tests for crud.plan_block (review sprint: plan vs actual, overdue, at-risk, stale)."""
import datetime as dt

from app import crud, models
from .factories import make_project, make_task, make_update, days_ago

S = models.Status

TODAY = dt.date.today()


def _proj(db, start_offset=-10, target_offset=10, **kw):
    return make_project(
        db,
        start_date=TODAY + dt.timedelta(days=start_offset),
        target_date=TODAY + dt.timedelta(days=target_offset),
        **kw,
    )


# ---------- expected vs actual ----------
def test_expected_pct_linear_midpoint(db):
    p = _proj(db, start_offset=-10, target_offset=10)
    make_task(db, p, progress_pct=30)
    make_task(db, p, title="Task 2", progress_pct=50)
    row = crud.plan_block([p], p.tasks)["per_project"][0]
    assert row["expected_pct"] == 50
    assert row["actual_pct"] == 40
    assert row["delta"] == -10
    assert row["days_left"] == 10


def test_expected_pct_clamped_past_target(db):
    p = _proj(db, start_offset=-30, target_offset=-10)
    make_task(db, p, progress_pct=80)
    row = crud.plan_block([p], p.tasks)["per_project"][0]
    assert row["expected_pct"] == 100
    assert row["days_left"] == -10


def test_expected_pct_none_without_dates(db):
    p = make_project(db)  # no start/target dates
    make_task(db, p, progress_pct=60)
    row = crud.plan_block([p], p.tasks)["per_project"][0]
    assert row["expected_pct"] is None
    assert row["delta"] is None
    assert row["actual_pct"] == 60


# ---------- overdue ----------
def test_overdue_excludes_done_and_future(db):
    p = _proj(db)
    late = make_task(db, p, title="Late", due_date=TODAY - dt.timedelta(days=2))
    make_task(db, p, title="Done late", status=S.done, due_date=TODAY - dt.timedelta(days=2))
    make_task(db, p, title="Future", due_date=TODAY + dt.timedelta(days=30))
    plan = crud.plan_block([p], p.tasks)
    assert [t["title"] for t in plan["overdue"]] == ["Late"]
    assert plan["overdue"][0]["days_left"] == -2
    assert late.id == plan["overdue"][0]["id"]


# ---------- at risk ----------
def test_at_risk_close_deadline_low_progress_or_blocked(db):
    p = _proj(db)
    make_task(db, p, title="Blocked soon", status=S.blocked, progress_pct=90,
              due_date=TODAY + dt.timedelta(days=3))
    make_task(db, p, title="Slow soon", progress_pct=20,
              due_date=TODAY + dt.timedelta(days=5))
    make_task(db, p, title="Nearly done soon", progress_pct=90,
              due_date=TODAY + dt.timedelta(days=3))
    make_task(db, p, title="Slow but far", progress_pct=20,
              due_date=TODAY + dt.timedelta(days=30))
    plan = crud.plan_block([p], p.tasks)
    titles = {t["title"] for t in plan["at_risk"]}
    assert titles == {"Blocked soon", "Slow soon"}


def test_overdue_task_not_double_counted_as_at_risk(db):
    p = _proj(db)
    make_task(db, p, title="Late", progress_pct=10, due_date=TODAY - dt.timedelta(days=1))
    plan = crud.plan_block([p], p.tasks)
    assert [t["title"] for t in plan["overdue"]] == ["Late"]
    assert plan["at_risk"] == []


# ---------- stale ----------
def test_stale_old_or_never_updated(db):
    p = _proj(db)
    old = make_task(db, p, title="Old news")
    make_update(db, old, created_at=days_ago(10))
    fresh = make_task(db, p, title="Fresh")
    make_update(db, fresh, created_at=days_ago(1))
    make_task(db, p, title="Silent")  # never reported on
    done = make_task(db, p, title="Done quiet", status=S.done)
    make_update(db, done, created_at=days_ago(30))
    db.refresh(p)
    plan = crud.plan_block([p], p.tasks)
    by_title = {t["title"]: t for t in plan["stale"]}
    assert set(by_title) == {"Old news", "Silent"}
    assert by_title["Old news"]["days_since_update"] == 10
    assert by_title["Silent"]["days_since_update"] is None


# ---------- wired into the dashboard payload ----------
def test_dashboard_metrics_includes_plan(db):
    p = _proj(db, start_offset=-5, target_offset=5)
    make_task(db, p, progress_pct=50, due_date=TODAY - dt.timedelta(days=1))
    data = crud.dashboard_metrics(db)
    assert data["plan"]["per_project"][0]["expected_pct"] == 50
    assert len(data["plan"]["overdue"]) == 1
