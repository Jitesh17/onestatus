"""Tests that the bundled demo seed (app/seed_demo.py) stays neutral.

The repository is public: the demo data must never contain internal product names or
real employee names. The word list below is the historical set that was renamed away.
"""
from app import crud, models, seed_demo

# Strings that must never appear in the bundled demo dataset.
INTERNAL_STRINGS = ["bravia", "xperia", "sony", "jitesh", "neeraj", "shivam",
                    "abhishake", "tanaka", "sato", "tokyo"]


def test_seed_demo_idempotent(db):
    seed_demo.run()
    counts1 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    seed_demo.run()
    counts2 = (db.query(models.Project).count(), db.query(models.Task).count(),
               db.query(models.Update).count(), db.query(models.Person).count())
    assert counts1 == counts2
    assert counts1[0] == 3 and counts1[3] == 6


def test_seed_demo_dashboard_renders(db):
    seed_demo.run()
    m = crud.dashboard_metrics(db)
    assert m["totals"]["projects"] == 3
    assert m["open_blockers"] > 0
    assert len(m["trends"]["progress"]) > 10
    assert len(m["per_team"]) == 3
    assert len(m["per_person"]) == 6


def test_seed_demo_contains_no_internal_strings(db):
    seed_demo.run()
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
        assert word not in blob, f"internal string {word!r} leaked into the demo seed"
