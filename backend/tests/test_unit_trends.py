"""Unit tests for crud.trend_series."""
import datetime as dt

from app import crud, models
from .factories import make_project, make_task, make_update, make_person, days_ago

S = models.Status
SV = models.Severity


def test_trends_empty_db(db):
    assert crud.trend_series(db) == {"progress": [], "blockers": []}


def test_trends_progress_carry_forward(db):
    p = make_project(db)
    t = make_task(db, p, progress_pct=50)
    make_update(db, t, created_at=days_ago(4), progress_pct=10)
    make_update(db, t, created_at=days_ago(2), progress_pct=30)
    series = crud.trend_series(db)["progress"]
    by_date = {pt["date"]: pt["value"] for pt in series}
    assert by_date[days_ago(4).date().isoformat()] == 10
    assert by_date[days_ago(3).date().isoformat()] == 10  # carried forward
    assert by_date[days_ago(2).date().isoformat()] == 30
    assert by_date[dt.date.today().isoformat()] == 30


def test_trends_snapshotless_task_contributes_flat_line(db):
    p = make_project(db)
    t1 = make_task(db, p, title="snapped", progress_pct=0)
    make_task(db, p, title="legacy", progress_pct=80)
    make_update(db, t1, created_at=days_ago(3), progress_pct=20)
    series = crud.trend_series(db)["progress"]
    # mean of (20 carried) and the legacy task's constant 80 on every day
    assert all(pt["value"] == 50 for pt in series)


def test_trends_blocker_burndown_never_negative(db):
    p = make_project(db)
    t = make_task(db, p)
    # A resolve with no recorded open would push the raw sum negative.
    make_update(db, t, created_at=days_ago(3),
                blockers=[("ghost", SV.medium, None, "resolved")])
    make_update(db, t, created_at=days_ago(1), blockers=[("real", SV.medium)])
    by_date = {pt["date"]: pt["value"] for pt in crud.trend_series(db)["blockers"]}
    assert all(v >= 0 for v in by_date.values())
    # Day of the ghost resolve: raw sum is -1, clamped to 0.
    assert by_date[days_ago(3).date().isoformat()] == 0
    # The later open cancels against the ghost resolve in the cumulative sum.
    assert by_date[days_ago(1).date().isoformat()] == 0


def test_trends_blocker_open_then_resolve_steps_down(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, created_at=days_ago(5), blockers=[("gpu", SV.medium)])
    make_update(db, t, created_at=days_ago(2),
                blockers=[("gpu", SV.medium, None, "resolved")])
    by_date = {pt["date"]: pt["value"] for pt in crud.trend_series(db)["blockers"]}
    assert by_date[days_ago(5).date().isoformat()] == 1
    assert by_date[days_ago(2).date().isoformat()] == 0


def test_trends_axis_sampled_and_end_included(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, created_at=days_ago(200), progress_pct=5)
    series = crud.trend_series(db)["progress"]
    assert len(series) <= crud.TREND_MAX_POINTS + 1
    assert series[-1]["date"] == dt.date.today().isoformat()


def test_trends_inverted_range_empty(db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, created_at=days_ago(2), progress_pct=10)
    cfg = {"date_from": (dt.date.today() + dt.timedelta(days=5)).isoformat()}
    assert crud.trend_series(db, cfg) == {"progress": [], "blockers": []}


def test_trends_respect_person_scope(db):
    make_person(db, "Neeraj", team="Display Systems")
    p = make_project(db)
    t1 = make_task(db, p, title="mine", assignee="Neeraj")
    t2 = make_task(db, p, title="theirs", assignee="Shivam")
    make_update(db, t1, created_at=days_ago(2), progress_pct=40)
    make_update(db, t2, created_at=days_ago(2), progress_pct=90)
    series = crud.trend_series(db, {"person": "Neeraj"})["progress"]
    assert series[-1]["value"] == 40  # Shivam's 90 excluded


def test_trends_respect_project_filter(db):
    p1, p2 = make_project(db, "P1"), make_project(db, "P2")
    t1, t2 = make_task(db, p1), make_task(db, p2)
    make_update(db, t1, created_at=days_ago(2), progress_pct=20)
    make_update(db, t2, created_at=days_ago(2), progress_pct=100)
    series = crud.trend_series(db, {"project": "P1"})["progress"]
    assert series[-1]["value"] == 20
