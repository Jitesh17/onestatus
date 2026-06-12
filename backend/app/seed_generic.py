"""Neutral sample data: same shape as seed_demo (3 projects, 7 tasks, history, roster)
but with generic project and people names. Used for the README screenshots and for
anyone who wants demo data without the internal project names.

Additive and idempotent through the seed_demo machinery: only inserts a project if its
name is not already present. Do not run it on top of seed_demo data unless you want
both datasets side by side.

Run from the backend folder:  python -m app.seed_generic
"""
import datetime as dt

from . import models, seed_demo

S = models.Status
SV = models.Severity

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

# task title -> [(days_ago, pct, status)] oldest-first; same shapes as seed_demo so the
# trend charts tell the same story (rising progress, one blocked plateau, one done arc).
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

# One blocker that opens then resolves, stepping the burn-down line.
HISTORY_BLOCKERS = {
    ("Push notification service", 15): ("Staging cluster maintenance window", SV.medium, "Casey", "open"),
    ("Push notification service", 9): ("Staging cluster maintenance window", SV.medium, "Casey", "resolved"),
}

ORG = [
    ("Alex", None, "Platform", "Engineering"),
    ("Sam", None, "Platform", "Engineering"),
    ("Casey", None, "Mobile", "Engineering"),
    ("Jordan", None, "Mobile", "Engineering"),
    ("Yamada-san", "山田さん", "Product Ops", "Operations"),
    ("Suzuki-san", "鈴木さん", "Product Ops", "Operations"),
]


def run():
    seed_demo.run(demo=DEMO, org=ORG, history=HISTORY, history_blockers=HISTORY_BLOCKERS)


if __name__ == "__main__":
    run()
