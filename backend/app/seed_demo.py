"""Richer demo data so the manager dashboard (week 5) shows meaningful KPIs.

Additive and idempotent: only inserts a project if its name is not already present, so
it is safe to run on top of existing data (including the small week-1 seed). Mirrors the
eval world (3 projects, ~7 tasks) and spreads tasks across all statuses, with updates
carrying blockers, risks, and next steps.

Run from the backend folder:  python -m app.seed_demo
"""
import datetime as dt
from .database import SessionLocal, Base, engine
from . import models

Base.metadata.create_all(bind=engine)

S = models.Status
SV = models.Severity

# Each project: meta + tasks (title, title_ja, assignee, status, progress) + updates.
DEMO = [
    {
        "name": "BRAVIA Panel Calibration", "name_ja": "ブラビア パネル キャリブレーション",
        "owner": "Jitesh", "status": S.in_progress,
        "start": dt.date(2026, 6, 1), "target": dt.date(2026, 9, 30),
        "tasks": [
            {"title": "Color uniformity test rig", "assignee": "Neeraj", "status": S.in_progress, "pct": 60},
            {"title": "Japan-side review pipeline", "title_ja": "日本側レビュー パイプライン",
             "assignee": "Abhishake", "status": S.blocked, "pct": 20},
            {"title": "Calibration dataset prep", "assignee": "Neeraj", "status": S.in_progress, "pct": 45},
        ],
        "updates": [
            {"task": "Japan-side review pipeline", "author": "Abhishake", "lang": "en", "source": "text",
             "text": "Review pipeline blocked on sample data access from Japan side.",
             "blockers": [("Waiting on sample data approval from Tokyo", SV.high, "Tokyo PMO", "open"),
                          ("Review tool license expired", SV.medium, None, "open")],
             "risks": [("Approval slipping past mid-June endangers the September demo", "high",
                        "Escalate to Tokyo PMO weekly", None)],
             "next_steps": [("Follow up with Tokyo PMO on data approval", "Jitesh", dt.date(2026, 6, 15))]},
            {"task": "Color uniformity test rig", "author": "Neeraj", "lang": "en", "source": "voice",
             "text": "Test rig about 60 percent done, wrapping up sensor mounts by Friday.",
             "next_steps": [("Finish remaining sensor mounts", "Neeraj", dt.date(2026, 6, 19))]},
        ],
    },
    {
        "name": "Xperia Mic Array Tuning", "name_ja": "エクスペリア マイクアレイ チューニング",
        "owner": "Shivam", "status": S.in_progress,
        "start": dt.date(2026, 5, 15), "target": dt.date(2026, 8, 31),
        "tasks": [
            {"title": "Noise suppression model", "assignee": "Shivam", "status": S.done, "pct": 100},
            {"title": "Field recording collection", "assignee": "Abhishake", "status": S.in_progress, "pct": 55},
        ],
        "updates": [
            {"task": "Noise suppression model", "author": "Shivam", "lang": "en", "source": "text",
             "text": "Noise suppression model done and signed off.", "next_steps": []},
            {"task": "Field recording collection", "author": "Abhishake", "lang": "en", "source": "text",
             "text": "Field recording at 55 percent, on track.",
             "risks": [("Monsoon may delay outdoor recordings next month", "medium",
                        "Do indoor sessions as backup", None)],
             "next_steps": [("Schedule indoor backup sessions", "Abhishake", None)]},
        ],
    },
    {
        "name": "Meeting Diarization Tool", "name_ja": "会議ダイアライゼーション ツール",
        "owner": "Jitesh", "status": S.in_progress,
        "start": dt.date(2026, 6, 5), "target": dt.date(2026, 10, 15),
        "tasks": [
            {"title": "Speaker separation module", "assignee": "Shivam", "status": S.in_progress, "pct": 40},
            {"title": "Japanese ASR accuracy test", "title_ja": "日本語ASR精度テスト",
             "assignee": "Abhishake", "status": S.not_started, "pct": 0},
        ],
        "updates": [
            {"task": "Speaker separation module", "author": "Shivam", "lang": "ja", "source": "voice",
             "text": "話者分離モジュールは40パーセント。重なり音声の処理が残っています。",
             "blockers": [("GPU server fully booked this week", SV.medium, None, "open")],
             "next_steps": [("重なり音声の処理を行う", "Shivam", None)]},
        ],
    },
]


def run():
    db = SessionLocal()
    try:
        existing = {p.name for p in db.query(models.Project).all()}
        added = 0
        for d in DEMO:
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
    finally:
        db.close()


if __name__ == "__main__":
    run()
