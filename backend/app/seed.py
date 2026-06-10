"""Seed a little demo data so the UI has something to show on first run.

Run from the backend folder:  python -m app.seed
Safe to run repeatedly; it skips seeding if projects already exist.
"""
import datetime as dt
from .database import SessionLocal, Base, engine
from . import models

Base.metadata.create_all(bind=engine)


def run():
    db = SessionLocal()
    try:
        if db.query(models.Project).count() > 0:
            print("Data already present, skipping seed.")
            return

        p = models.Project(
            name="BRAVIA Panel Calibration",
            name_ja="ブラビア パネル キャリブレーション",
            owner="Jitesh",
            status=models.Status.in_progress,
            start_date=dt.date(2026, 6, 1),
            target_date=dt.date(2026, 9, 30),
        )
        db.add(p)
        db.flush()

        t1 = models.Task(project_id=p.id, title="Color uniformity test rig",
                         assignee="Neeraj", status=models.Status.in_progress, progress_pct=60)
        t2 = models.Task(project_id=p.id, title="Japan-side review pipeline",
                         title_ja="日本側レビュー パイプライン",
                         assignee="Abhishake", status=models.Status.blocked, progress_pct=20)
        db.add_all([t1, t2])
        db.flush()

        u = models.Update(
            task_id=t2.id, author="Abhishake", language="en", source="text",
            raw_text="Review pipeline blocked on sample data access from Japan side.",
        )
        u.blockers = [models.Blocker(description="Waiting on sample data approval from Tokyo",
                                     severity=models.Severity.high, owner="Tokyo PMO")]
        u.next_steps = [models.NextStep(description="Follow up with Tokyo PMO on data approval",
                                        owner="Jitesh", due_date=dt.date(2026, 6, 15))]
        db.add(u)
        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
