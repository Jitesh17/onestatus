"""Tests for the neutral sample seed (app/seed_generic.py)."""
from app import crud, models, seed_generic

# Strings from the internal demo data that must never appear in the generic dataset.
INTERNAL_STRINGS = ["bravia", "xperia", "sony", "jitesh", "neeraj", "shivam",
                    "abhishake", "tanaka", "sato", "tokyo"]


def test_seed_generic_idempotent(db):
    seed_generic.run()
    counts1 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    seed_generic.run()
    counts2 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    assert counts1 == counts2
    assert counts1[0] == 3 and counts1[3] == 6


def test_seed_generic_dashboard_renders(db):
    seed_generic.run()
    m = crud.dashboard_metrics(db)
    assert m["totals"]["projects"] == 3
    assert m["open_blockers"] > 0
    assert len(m["trends"]["progress"]) > 10
    assert len(m["per_team"]) == 3
    assert len(m["per_person"]) == 6


def test_seed_generic_contains_no_internal_strings(db):
    seed_generic.run()
    texts = []
    for p in db.query(models.Project).all():
        texts += [p.name, p.name_ja or "", p.owner or ""]
    for t in db.query(models.Task).all():
        texts += [t.title, t.title_ja or "", t.assignee or ""]
    for u in db.query(models.Update).all():
        texts += [u.raw_text or "", u.author or ""]
    for person in db.query(models.Person).all():
        texts += [person.name, person.name_ja or "", person.team or "", person.department or ""]
    for b in db.query(models.Blocker).all():
        texts += [b.description or "", b.owner or ""]
    for r in db.query(models.Risk).all():
        texts += [r.description or "", r.mitigation or "", r.owner or ""]
    for n in db.query(models.NextStep).all():
        texts += [n.description or "", n.owner or ""]
    blob = " ".join(texts).lower()
    for word in INTERNAL_STRINGS:
        assert word not in blob, f"internal string {word!r} leaked into the generic seed"
