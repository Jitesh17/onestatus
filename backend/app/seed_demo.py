"""Richer demo data so the manager dashboard (week 5) shows meaningful KPIs.

Additive and idempotent: only inserts a project if its name is not already present, so
it is safe to run on top of existing data (including the small week-1 seed). Mirrors the
eval world (3 projects, ~7 tasks) and spreads tasks across all statuses, with updates
carrying blockers, risks, and next steps. The README screenshots use this dataset.

Run from the backend folder:  python -m app.seed_demo
"""
import datetime as dt
from .database import SessionLocal, Base, engine
from . import models, migrate

Base.metadata.create_all(bind=engine)
migrate.run(engine)  # adds new nullable columns (e.g. updates.status) to an existing DB

S = models.Status
SV = models.Severity

# Each project: meta + tasks (title, title_ja, assignee, status, progress) + updates.
DEMO = [
    {
        "name": "Website Redesign", "name_ja": "ウェブサイト刷新",
        "owner": "Alex", "status": S.in_progress,
        "start": dt.date(2026, 6, 1), "target": dt.date(2026, 9, 30),
        "tasks": [
            {"title": "Checkout flow rework", "assignee": "Sam", "status": S.in_progress, "pct": 60},
            {"title": "Design review pipeline", "title_ja": "デザインレビュー パイプライン",
             "assignee": "Jordan", "status": S.blocked, "pct": 20},
            {"title": "Content migration", "assignee": "Sam", "status": S.in_progress, "pct": 45},
        ],
        "updates": [
            {"task": "Design review pipeline", "author": "Jordan", "lang": "en", "source": "text",
             "text": "Design review pipeline blocked on brand asset approval.",
             "blockers": [("Waiting on brand asset approval", SV.high, "Design Ops", "open"),
                          ("Review tool license expired", SV.medium, None, "open")],
             "risks": [("Approval slipping past mid-June endangers the September launch", "high",
                        "Escalate to Design Ops weekly", None)],
             "next_steps": [("Follow up with Design Ops on asset approval", "Yamada-san", dt.date(2026, 6, 15))]},
            {"task": "Checkout flow rework", "author": "Sam", "lang": "en", "source": "voice",
             "text": "Checkout rework about 60 percent done, wrapping up the payment screens by Friday.",
             "next_steps": [("Finish remaining payment screens", "Sam", dt.date(2026, 6, 19))]},
        ],
    },
    {
        "name": "Mobile App v2", "name_ja": "モバイルアプリ v2",
        "owner": "Casey", "status": S.in_progress,
        "start": dt.date(2026, 5, 15), "target": dt.date(2026, 8, 31),
        "tasks": [
            {"title": "Push notification service", "assignee": "Casey", "status": S.done, "pct": 100},
            {"title": "Beta feedback collection", "assignee": "Jordan", "status": S.in_progress, "pct": 55},
        ],
        "updates": [
            {"task": "Push notification service", "author": "Casey", "lang": "en", "source": "text",
             "text": "Push notification service done and signed off.", "next_steps": []},
            {"task": "Beta feedback collection", "author": "Jordan", "lang": "en", "source": "text",
             "text": "Beta feedback collection at 55 percent, on track.",
             "risks": [("Summer holidays may slow beta responses next month", "medium",
                        "Recruit extra beta testers as backup", None)],
             "next_steps": [("Recruit additional beta testers", "Jordan", None)]},
        ],
    },
    {
        "name": "Data Pipeline Migration", "name_ja": "データ基盤移行",
        "owner": "Alex", "status": S.in_progress,
        "start": dt.date(2026, 6, 5), "target": dt.date(2026, 10, 15),
        "tasks": [
            {"title": "ETL cutover module", "assignee": "Casey", "status": S.in_progress, "pct": 40},
            {"title": "Legacy data validation", "title_ja": "旧データ検証",
             "assignee": "Jordan", "status": S.not_started, "pct": 0},
        ],
        "updates": [
            {"task": "ETL cutover module", "author": "Casey", "lang": "ja", "source": "voice",
             "text": "ETLカットオーバーモジュールは40パーセント。残りはエラー処理の実装です。",
             "blockers": [("Staging server fully booked this week", SV.medium, None, "open")],
             "next_steps": [("エラー処理の実装を行う", "Casey", None)]},
        ],
    },
]


# ---------- Backdated history (trends sprint) ----------
# ~3 weeks of progress snapshots per task so the trend charts have a story: rising
# progress_pct, status transitions, and one blocker that opens then resolves.
# task title -> [(days_ago, pct, status)] oldest-first, ending near the task's current values.
HISTORY = {
    "Checkout flow rework": [(21, 10, "in_progress"), (17, 25, "in_progress"),
                             (12, 35, "in_progress"), (7, 50, "in_progress"), (2, 60, "in_progress")],
    "Design review pipeline": [(20, 5, "in_progress"), (14, 15, "in_progress"),
                               (8, 20, "blocked"), (3, 20, "blocked")],
    "Content migration": [(19, 10, "in_progress"), (11, 30, "in_progress"), (4, 45, "in_progress")],
    "Push notification service": [(21, 55, "in_progress"), (15, 75, "in_progress"),
                                  (9, 90, "in_progress"), (5, 100, "done")],
    "Beta feedback collection": [(18, 15, "in_progress"), (10, 35, "in_progress"), (3, 55, "in_progress")],
    "ETL cutover module": [(16, 10, "in_progress"), (9, 25, "in_progress"), (2, 40, "in_progress")],
}

# (task title, days_ago) -> blocker tuple attached to that history update. The same
# description appears once "open" and later "resolved", stepping the burn-down line.
HISTORY_BLOCKERS = {
    ("Push notification service", 15): ("Staging cluster maintenance window", SV.medium, "Casey", "open"),
    ("Push notification service", 9): ("Staging cluster maintenance window", SV.medium, "Casey", "resolved"),
}


# ---------- Org roster (report-scenarios sprint) ----------
# Powers the team/person rollups and the preset team picker. Names match the free-text
# assignee/author/owner values used above; matching is by name at aggregation time.
ORG = [
    ("Alex", None, "Platform", "Engineering"),
    ("Sam", None, "Platform", "Engineering"),
    ("Casey", None, "Mobile", "Engineering"),
    ("Jordan", None, "Mobile", "Engineering"),
    ("Yamada-san", "山田さん", "Product Ops", "Operations"),
    ("Suzuki-san", "鈴木さん", "Product Ops", "Operations"),
]


def seed_people(db, org=ORG):
    """Idempotent by name: a person already in the table is never touched."""
    existing = {p.name for p in db.query(models.Person).all()}
    added = 0
    for name, name_ja, team, dept in org:
        if name in existing:
            continue
        db.add(models.Person(name=name, name_ja=name_ja, team=team, department=dept))
        added += 1
    db.commit()
    if added:
        print(f"Org roster seeded: {added} person(s).")
    else:
        print("Org roster already present, nothing added.")


def _ago(days: int) -> dt.datetime:
    return (dt.datetime.utcnow() - dt.timedelta(days=days)).replace(
        hour=10, minute=0, second=0, microsecond=0)


def seed_history(db, history=HISTORY, history_blockers=HISTORY_BLOCKERS):
    """Idempotent: any update older than ~2 days is the marker that history exists."""
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=2)
    if db.query(models.Update).filter(models.Update.created_at < cutoff).first():
        print("Backdated history already present, nothing added.")
        return
    tasks = {t.title: t for t in db.query(models.Task).all()}
    n = 0
    for title, points in history.items():
        task = tasks.get(title)
        if not task:
            continue
        for days_ago, pct, status in points:
            upd = models.Update(
                task_id=task.id, author=task.assignee, language="en", source="text",
                raw_text=f"{title}: progress at {pct} percent.",
                created_at=_ago(days_ago), status=status, progress_pct=pct,
            )
            blk = history_blockers.get((title, days_ago))
            if blk:
                upd.blockers = [models.Blocker(description=blk[0], severity=blk[1],
                                               owner=blk[2], status=blk[3])]
            db.add(upd)
            n += 1
    db.commit()
    print(f"Backdated history added: {n} update(s).")


def run(demo=DEMO, org=ORG, history=HISTORY, history_blockers=HISTORY_BLOCKERS):
    """Seed the given dataset (defaults: the bundled demo data)."""
    db = SessionLocal()
    try:
        seed_people(db, org)
        existing = {p.name for p in db.query(models.Project).all()}
        added = 0
        for d in demo:
            if d["name"] in existing:
                continue
            p = models.Project(name=d["name"], name_ja=d["name_ja"], owner=d["owner"],
                               status=d["status"], start_date=d["start"], target_date=d["target"])
            db.add(p)
            db.flush()
            tasks_by_title = {}
            for t in d["tasks"]:
                obj = models.Task(project_id=p.id, title=t["title"], title_ja=t.get("title_ja"),
                                  assignee=t.get("assignee"), status=t["status"], progress_pct=t["pct"])
                db.add(obj)
                db.flush()
                tasks_by_title[t["title"]] = obj
            for u in d.get("updates", []):
                upd = models.Update(task_id=tasks_by_title[u["task"]].id, author=u.get("author"),
                                    language=u.get("lang", "en"), source=u.get("source", "text"),
                                    raw_text=u.get("text"))
                upd.blockers = [models.Blocker(description=b[0], severity=b[1], owner=b[2], status=b[3])
                                for b in u.get("blockers", [])]
                upd.risks = [models.Risk(description=r[0], impact=r[1], mitigation=r[2], owner=r[3])
                             for r in u.get("risks", [])]
                upd.next_steps = [models.NextStep(description=n[0], owner=n[1], due_date=n[2])
                                  for n in u.get("next_steps", [])]
                db.add(upd)
            added += 1
        db.commit()
        if added:
            print(f"Demo seed complete. Added {added} project(s).")
        else:
            print("Demo projects already present, nothing added.")
        seed_history(db, history, history_blockers)
    finally:
        db.close()


if __name__ == "__main__":
    run()
