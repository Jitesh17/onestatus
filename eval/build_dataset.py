"""Builds the OneStatus evaluation dataset.

Outputs:
  eval/world.json          the fake world: projects, tasks, people (for name matching)
  eval/updates_eval.jsonl  labeled examples: free-form update -> correct extraction

Each example is a (input_text -> expected) pair. In week 2/3 we run the local LLM
on input_text and score its output against expected. This is the go/no-go data.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# The fake world. Updates below refer only to these projects, tasks, and people.
# Mirrors the demo seed (app/seed_demo.py) so the eval and the demo tell the
# same story.
# ---------------------------------------------------------------------------
WORLD = {
    "people": ["Alex", "Sam", "Casey", "Jordan", "Yamada-san", "Suzuki-san"],
    "projects": [
        {
            "name": "Website Redesign",
            "name_ja": "ウェブサイト刷新",
            "tasks": [
                "Checkout flow rework",
                "Design review pipeline",
                "Content migration",
            ],
        },
        {
            "name": "Mobile App v2",
            "name_ja": "モバイルアプリ v2",
            "tasks": [
                "Push notification service",
                "Beta feedback collection",
            ],
        },
        {
            "name": "Data Pipeline Migration",
            "name_ja": "データ基盤移行",
            "tasks": [
                "ETL cutover module",
                "Legacy data validation",
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Labeled examples. expected fields follow the extraction schema:
#   project, task, status, progress_pct, blockers[], risks[], owners[],
#   next_steps[], period
# Use null / [] where the update does not state something.
# status: not_started | in_progress | blocked | done
# severity: low | medium | high
# ---------------------------------------------------------------------------
E = []

def add(id, situation, language, source, text, expected, notes):
    E.append({
        "id": id, "situation": situation, "language": language, "source": source,
        "input_text": text, "expected": expected, "notes": notes,
    })

# 1. Clean single update, explicit progress (EN)
add("ex_001", "clean single-task update with explicit progress", "en", "text",
    "Checkout flow rework is going well, we're about 60 percent done. Should wrap up the remaining payment screens by Friday.",
    {"project": "Website Redesign", "task": "Checkout flow rework",
     "status": "in_progress", "progress_pct": 60, "blockers": [], "risks": [],
     "owners": [], "next_steps": [{"description": "Finish remaining payment screens", "owner": None, "due_date": "Friday"}],
     "period": None},
    "Baseline easy case. Tests progress parsing and a single next step.")

# 2. Multiple blockers + a risk (EN)
add("ex_002", "multiple blockers plus a risk", "en", "text",
    "Design review pipeline is stuck. Two things blocking us: we still don't have brand asset approval from the head office, and the review tool license expired. Also flagging a risk that if approval slips past mid-June the whole September launch timeline is at risk.",
    {"project": "Website Redesign", "task": "Design review pipeline",
     "status": "blocked", "progress_pct": None,
     "blockers": [
         {"description": "No brand asset approval from the head office", "severity": "high", "owner": None},
         {"description": "Review tool license expired", "severity": "medium", "owner": None}],
     "risks": [{"description": "Approval slipping past mid-June endangers the September launch", "likelihood": None, "impact": "high", "mitigation": None, "owner": None}],
     "owners": [], "next_steps": [], "period": None},
    "Tests multiple blockers with different severities and a separate risk.")

# 3. Terse update (EN)
add("ex_003", "very terse update", "en", "text",
    "Push notification service done. Starting beta feedback collection next.",
    {"project": "Mobile App v2", "task": "Push notification service",
     "status": "done", "progress_pct": 100, "blockers": [], "risks": [], "owners": [],
     "next_steps": [{"description": "Start beta feedback collection", "owner": None, "due_date": None}],
     "period": None},
    "Tests terse input and a next step that names a different known task.")

# 4. Rambling, verbose with filler (EN)
add("ex_004", "rambling update with filler", "en", "text",
    "So yeah this week was kind of busy, lots of meetings honestly, but on the ETL cutover module I managed to get the basic pipeline running, I'd say maybe a third of the way there, still need to implement the error handling which is the hard part. Nothing really blocking me right now.",
    {"project": "Data Pipeline Migration", "task": "ETL cutover module",
     "status": "in_progress", "progress_pct": 33, "blockers": [], "risks": [], "owners": [],
     "next_steps": [{"description": "Implement error handling", "owner": None, "due_date": None}],
     "period": None},
    "Tests pulling structure out of chatty filler and an approximate progress phrase.")

# 5. No blockers, progress + next step (EN)
add("ex_005", "progress and next step, no blockers", "en", "text",
    "Content migration is around 45 percent. Next I'll tag the remaining page batches and hand them to Sam for review.",
    {"project": "Website Redesign", "task": "Content migration",
     "status": "in_progress", "progress_pct": 45, "blockers": [], "risks": [],
     "owners": ["Sam"],
     "next_steps": [{"description": "Tag remaining page batches and hand to Sam for review", "owner": "Sam", "due_date": None}],
     "period": None},
    "Tests owner detection from a handoff phrase.")

# 6. Unknown project (no match) (EN)
add("ex_006", "mentions a project not in the world", "en", "text",
    "Made good progress on the CRM integration demo, about half done.",
    {"project": "unknown", "task": None, "status": "in_progress", "progress_pct": 50,
     "blockers": [], "risks": [], "owners": [], "next_steps": [], "period": None},
    "Tests that an unknown project is marked unknown, not force-matched.")

# 7. Two tasks in one update (EN)
add("ex_007", "two tasks mentioned in one update", "en", "text",
    "Quick double update: legacy data validation is at 70 percent and looking good. Separately, the ETL cutover module is blocked because the staging server is fully booked this week.",
    {"project": "Data Pipeline Migration", "task": "Legacy data validation",
     "status": "in_progress", "progress_pct": 70,
     "blockers": [], "risks": [], "owners": [], "next_steps": [], "period": None,
     "secondary": {"task": "ETL cutover module", "status": "blocked", "progress_pct": None,
                   "blockers": [{"description": "Staging server fully booked this week", "severity": "medium", "owner": None}]}},
    "Hard case: two tasks in one update. Tests whether the model splits them. 'secondary' holds the second task.")

# 8. Resolved blocker (EN)
add("ex_008", "a previously blocking item is now resolved", "en", "text",
    "Good news, the brand asset approval from the head office finally came through, so the design review pipeline is unblocked and moving again. Back to about 30 percent.",
    {"project": "Website Redesign", "task": "Design review pipeline",
     "status": "in_progress", "progress_pct": 30,
     "blockers": [{"description": "Brand asset approval from the head office", "severity": None, "owner": None, "status": "resolved"}],
     "risks": [], "owners": [], "next_steps": [], "period": None},
    "Tests a blocker marked resolved rather than open, and status flipping back to in_progress.")

# 9. Risk but no blocker (EN)
add("ex_009", "risk only, no blocker", "en", "text",
    "Beta feedback collection is on track at 55 percent. One risk worth noting: summer holidays may slow beta responses next month. Planning to recruit extra beta testers as backup.",
    {"project": "Mobile App v2", "task": "Beta feedback collection",
     "status": "in_progress", "progress_pct": 55, "blockers": [],
     "risks": [{"description": "Summer holidays may slow beta responses next month", "likelihood": "medium", "impact": "medium", "mitigation": "Recruit extra beta testers as backup", "owner": None}],
     "owners": [], "next_steps": [], "period": None},
    "Tests a risk with a mitigation, and no blocker.")

# 10. Ambiguous status (EN)
add("ex_010", "ambiguous status, no clear progress", "en", "text",
    "Looked into the checkout flow rework a bit this week.",
    {"project": "Website Redesign", "task": "Checkout flow rework",
     "status": "in_progress", "progress_pct": None, "blockers": [], "risks": [], "owners": [],
     "next_steps": [], "period": None},
    "Low-information input. Tests that the model does not invent progress or blockers. Confidence should be low.")

# 11. Clean update (JP)
add("ex_011", "clean update in Japanese", "ja", "text",
    "チェックアウトフローの改修は順調で、進捗はおよそ60パーセントです。残りの決済画面は金曜日までに完了予定です。",
    {"project": "Website Redesign", "task": "Checkout flow rework",
     "status": "in_progress", "progress_pct": 60, "blockers": [], "risks": [], "owners": [],
     "next_steps": [{"description": "残りの決済画面を完了する", "owner": None, "due_date": "金曜日"}],
     "period": None},
    "Japanese mirror of ex_001. Tests JP extraction into the same schema.")

# 12. Polite business JP with a blocker
add("ex_012", "polite business Japanese with a blocker", "ja", "text",
    "お疲れ様です。デザインレビューパイプラインの件ですが、本社からのブランド素材承認がまだ得られておらず、作業がブロックされている状況です。重要度は高いと考えております。",
    {"project": "Website Redesign", "task": "Design review pipeline",
     "status": "blocked", "progress_pct": None,
     "blockers": [{"description": "本社からのブランド素材承認が未取得", "severity": "high", "owner": None}],
     "risks": [], "owners": [], "next_steps": [], "period": None},
    "Tests polite business JP and severity inferred from 重要度は高い.")

# 13. Terse JP
add("ex_013", "terse Japanese update", "ja", "text",
    "プッシュ通知サービス完了。次はベータフィードバック収集に着手します。",
    {"project": "Mobile App v2", "task": "Push notification service",
     "status": "done", "progress_pct": 100, "blockers": [], "risks": [], "owners": [],
     "next_steps": [{"description": "ベータフィードバック収集に着手する", "owner": None, "due_date": None}],
     "period": None},
    "JP terse done + next step. Mirror of ex_003.")

# 14. JP with progress + next steps + owner
add("ex_014", "Japanese with progress, owner handoff", "ja", "text",
    "コンテンツ移行は約45パーセントです。次は残りのページバッチにタグ付けを行い、レビューのためサムさんに渡します。",
    {"project": "Website Redesign", "task": "Content migration",
     "status": "in_progress", "progress_pct": 45, "blockers": [], "risks": [],
     "owners": ["Sam"],
     "next_steps": [{"description": "残りのページバッチにタグ付けし、サムさんにレビューを依頼する", "owner": "Sam", "due_date": None}],
     "period": None},
    "Tests JP owner detection where a name is written in katakana (サム -> Sam).")

# 15. JP risk
add("ex_015", "Japanese risk note", "ja", "text",
    "ベータフィードバック収集は55パーセントで順調です。リスクとして、来月は夏季休暇のためベータ回答が遅れる可能性があります。対策として追加のベータテスターを募集する予定です。",
    {"project": "Mobile App v2", "task": "Beta feedback collection",
     "status": "in_progress", "progress_pct": 55, "blockers": [],
     "risks": [{"description": "来月、夏季休暇のためベータ回答が遅れる可能性", "likelihood": "medium", "impact": "medium", "mitigation": "追加のベータテスターを募集", "owner": None}],
     "owners": [], "next_steps": [], "period": None},
    "JP risk with mitigation. Mirror of ex_009.")

# 16. Mixed EN-JP code-switch
add("ex_016", "code-switching English and Japanese", "ja", "text",
    "ETL cutover module の進捗ですが、basic pipeline は動くようになりました。だいたい30パーセントくらいです。error handling の実装がまだ残っています。",
    {"project": "Data Pipeline Migration", "task": "ETL cutover module",
     "status": "in_progress", "progress_pct": 30, "blockers": [], "risks": [], "owners": [],
     "next_steps": [{"description": "error handling の実装を行う", "owner": None, "due_date": None}],
     "period": None},
    "Bilingual-team reality: English technical terms inside Japanese sentences. Tests robustness to code-switching.")

# 17. Mixed code-switch 2 with blocker
add("ex_017", "code-switching with a blocker", "en", "text",
    "Mobile app の push notification service は基本的にできたけど、staging サーバーが足りなくて load testing が blocked です。",
    {"project": "Mobile App v2", "task": "Push notification service",
     "status": "blocked", "progress_pct": None,
     "blockers": [{"description": "Insufficient staging servers for load testing", "severity": "medium", "owner": None}],
     "risks": [], "owners": [], "next_steps": [], "period": None},
    "Reverse code-switch: Japanese grammar wrapping English terms. Tests blocker detection across languages.")

# 18. Explicit dates and owners (EN)
add("ex_018", "explicit owners and due dates", "en", "text",
    "ETL cutover module update: Casey is taking over the error-handling work, target June 20. Jordan will run the validation benchmark after that. Currently around 40 percent.",
    {"project": "Data Pipeline Migration", "task": "ETL cutover module",
     "status": "in_progress", "progress_pct": 40, "blockers": [], "risks": [],
     "owners": ["Casey", "Jordan"],
     "next_steps": [
         {"description": "Take over error-handling work", "owner": "Casey", "due_date": "2026-06-20"},
         {"description": "Run the validation benchmark", "owner": "Jordan", "due_date": None}],
     "period": None},
    "Tests multiple owners and an explicit date normalized to ISO.")

# 19. Done/completed (EN)
add("ex_019", "completed task", "en", "text",
    "Legacy data validation is finished and signed off. Final pass rate hit our target.",
    {"project": "Data Pipeline Migration", "task": "Legacy data validation",
     "status": "done", "progress_pct": 100, "blockers": [], "risks": [], "owners": [],
     "next_steps": [], "period": None},
    "Clean done case in English.")

# 20. Done (JP)
add("ex_020", "completed task in Japanese", "ja", "text",
    "旧データ検証は完了し、承認も得られました。最終結果は目標を達成しています。",
    {"project": "Data Pipeline Migration", "task": "Legacy data validation",
     "status": "done", "progress_pct": 100, "blockers": [], "risks": [], "owners": [],
     "next_steps": [], "period": None},
    "JP done case. Mirror of ex_019.")

# 21. Reporting period stated (EN)
add("ex_021", "update with an explicit reporting week", "en", "text",
    "Week of June 8: checkout flow rework moved from 60 to 75 percent. On track.",
    {"project": "Website Redesign", "task": "Checkout flow rework",
     "status": "in_progress", "progress_pct": 75, "blockers": [], "risks": [], "owners": [],
     "next_steps": [], "period": "Week of June 8"},
    "Tests period extraction and taking the latest progress value (75, not 60).")

# 22. Vague, low-extractable (EN)
add("ex_022", "vague update with little structure", "en", "text",
    "Things are moving along, nothing major to report this week.",
    {"project": "unknown", "task": None, "status": None, "progress_pct": None,
     "blockers": [], "risks": [], "owners": [], "next_steps": [], "period": None},
    "Almost no signal. Tests that the model returns empties instead of hallucinating. Confidence should be very low.")

# ---------------------------------------------------------------------------
# Validate labels before writing, so the golden data is internally consistent.
# ---------------------------------------------------------------------------
STATUS = {None, "not_started", "in_progress", "blocked", "done"}
SEV = {None, "low", "medium", "high"}
known_tasks = {t for p in WORLD["projects"] for t in p["tasks"]}
known_projects = {p["name"] for p in WORLD["projects"]} | {"unknown"}

errors = []
ids = set()
for ex in E:
    x = ex["expected"]
    if ex["id"] in ids:
        errors.append(f"{ex['id']}: duplicate id")
    ids.add(ex["id"])
    if x["status"] not in STATUS:
        errors.append(f"{ex['id']}: bad status {x['status']}")
    if x["progress_pct"] is not None and not (0 <= x["progress_pct"] <= 100):
        errors.append(f"{ex['id']}: progress out of range")
    if x["project"] not in known_projects:
        errors.append(f"{ex['id']}: project not in world: {x['project']}")
    if x["task"] is not None and x["task"] not in known_tasks:
        errors.append(f"{ex['id']}: task not in world: {x['task']}")
    for b in x["blockers"]:
        if b.get("severity") not in SEV:
            errors.append(f"{ex['id']}: bad severity {b.get('severity')}")
    for o in x["owners"]:
        if o not in WORLD["people"]:
            errors.append(f"{ex['id']}: owner not in world: {o}")

if errors:
    print("LABEL ERRORS:")
    print("\n".join(errors))
    raise SystemExit(1)

with open(os.path.join(HERE, "world.json"), "w", encoding="utf-8") as f:
    json.dump(WORLD, f, ensure_ascii=False, indent=2)

with open(os.path.join(HERE, "updates_eval.jsonl"), "w", encoding="utf-8") as f:
    for ex in E:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

# Quick summary
langs = {}
for ex in E:
    langs[ex["language"]] = langs.get(ex["language"], 0) + 1
print(f"Wrote {len(E)} examples. Languages: {langs}")
print("Labels validated, no errors.")
