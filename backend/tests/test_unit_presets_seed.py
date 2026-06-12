"""Unit tests for presets, seed_demo idempotency, and the startup column migration."""
from sqlalchemy import text

from app import crud, migrate, models, presets, schemas, seed_demo
from app.database import engine
from .factories import make_person


# ---------- presets ----------
def test_preset_configs_validate_as_viewconfig():
    for p in presets.PRESETS:
        cfg = {k: (v.replace("{team}", "Display Systems") if isinstance(v, str) else v)
               for k, v in p["config"].items()}
        validated = schemas.ViewConfig(**cfg)
        assert all(s in ("delivery per_project per_team per_person blockers risks "
                         "activity next_steps trends").split()
                   for s in validated.sections)


def test_preset_ids_unique_and_needs_team_consistent():
    ids = [p["id"] for p in presets.PRESETS]
    assert len(ids) == len(set(ids))
    for p in presets.PRESETS:
        has_placeholder = "{team}" in str(p["config"]) or "{team}" in p["nl_phrase"]
        assert p["needs_team"] == has_placeholder, p["id"]


def test_get_presets_teams_from_roster(db):
    make_person(db, "Neeraj", team="Display Systems")
    make_person(db, "Jitesh", team="Display Systems")
    make_person(db, "Shivam", team="Speech & Audio")
    out = presets.get_presets(db)
    assert out["teams"] == ["Display Systems", "Speech & Audio"]
    assert len(out["presets"]) == 6


def test_get_presets_empty_roster(db):
    out = presets.get_presets(db)
    assert out["teams"] == []
    assert len(out["presets"]) == 6


# ---------- seed idempotency ----------
def test_seed_demo_idempotent(db):
    seed_demo.run()
    counts1 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    seed_demo.run()
    counts2 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    assert counts1 == counts2
    assert counts1[0] == 3 and counts1[3] == 6


def test_seed_people_skips_existing(db):
    make_person(db, "Neeraj", team="Custom Team")
    seed_demo.seed_people(db)
    row = db.query(models.Person).filter(models.Person.name == "Neeraj").one()
    assert row.team == "Custom Team"  # untouched
    assert db.query(models.Person).count() == 6


def test_seeded_dashboard_has_history_and_rollups(seeded):
    m = crud.dashboard_metrics(seeded)
    assert m["totals"]["projects"] == 3
    assert len(m["trends"]["progress"]) > 10
    assert len(m["per_team"]) == 3
    assert len(m["per_person"]) == 6


# ---------- migrate ----------
def test_migrate_adds_missing_columns_and_is_idempotent(db):
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE updates DROP COLUMN status"))
        conn.execute(text("ALTER TABLE updates DROP COLUMN progress_pct"))
        conn.commit()
    migrate.run(engine)
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(updates)"))}
    assert {"status", "progress_pct"} <= cols
    migrate.run(engine)  # second run is a no-op, must not raise
