"""Local-LLM extraction: free-form update text -> structured draft.

Week 2. Calls a local Ollama model in JSON-constrained mode and grounds it in a
"world" (the known projects, tasks, and people) so it matches names instead of
inventing them. The output dict mirrors the eval `expected` schema exactly, so the
same function powers both the live `/extract` endpoint and `eval/run_eval.py`.

The model proposes; a human confirms in the UI before anything is saved. Nothing
here writes to the database.

Env:
  OLLAMA_URL    base URL of the Ollama server (default http://localhost:11434)
  OLLAMA_MODEL  default model name when the caller does not pass one (default qwen2.5:7b)
"""
import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# The shape we ask the model to fill. Mirrors eval `expected`. Kept as a literal
# in the prompt so the model sees the exact keys and the "leave empty" contract.
EMPTY_DRAFT = {
    "project": "unknown",
    "task": None,
    "status": None,
    "progress_pct": None,
    "blockers": [],
    "risks": [],
    "owners": [],
    "next_steps": [],
    "period": None,
    "confidence": 0.0,
}

STATUSES = ["not_started", "in_progress", "blocked", "done"]
SEVERITIES = ["low", "medium", "high"]


class ExtractorError(RuntimeError):
    """Raised when the local model is unreachable or returns unusable output."""


def build_world_prompt(world):
    """Render the world (projects EN+JA, tasks, people) into prompt text."""
    lines = ["Known projects and their tasks:"]
    for p in world.get("projects", []):
        ja = f" (JA: {p['name_ja']})" if p.get("name_ja") else ""
        lines.append(f"- {p['name']}{ja}")
        for t in p.get("tasks", []):
            lines.append(f"    - {t}")
    people = ", ".join(world.get("people", []))
    lines.append(f"Known people: {people}")
    return "\n".join(lines)


def _system_prompt(world):
    return f"""You convert a free-form project status update into a strict JSON object.

{build_world_prompt(world)}

Rules:
- Match the project and task to the known names above. Use the exact known name.
- "task" is the task the update is primarily reporting progress on. A task mentioned only as something to do NEXT belongs in next_steps, not in "task". (e.g. "X is done, starting Y next" -> task is X, and Y is a next_step.)
- If the update refers to a project NOT in the list, set "project" to "unknown" and "task" to null. Do not force a match.
- Do not invent facts. But DO infer status and capture next steps from how the update is phrased (see below) - those are stated, just not labeled.
- "status" is one of {STATUSES} or null. Infer it:
    * any update that describes ongoing work or reports any progress is "in_progress", even if it never says so ("looked into X", "got the pipeline running", "Shivam is taking over") -> in_progress;
    * "done"/"completed"/"finished"/"signed off"/"完了"/"完了し" -> done;
    * "blocked"/"stuck"/"waiting on"/"ブロック" -> blocked;
    * use null ONLY when the update gives no signal of any activity at all.
- "progress_pct" is an integer 0-100 or null. "done" implies 100.
- A blocker is something CURRENTLY stopping or slowing the work (no approval, expired license, server booked). A risk is something that MIGHT happen later (monsoon may delay, approval may slip). Never put a risk, a mitigation, or a next step into "blockers".
    * Each blocker: {{"description": str, "severity": one of {SEVERITIES} or null, "owner": str or null, "status": "open" or "resolved"}}.
- A risk is a possible future problem; keep its backup plan in the risk's "mitigation", NOT in next_steps.
    * Each risk: {{"description": str, "likelihood": str or null, "impact": str or null, "mitigation": str or null, "owner": str or null}}.
- next_steps: the actions the update actually proposes doing next. Trigger phrases: "next", "then", "after that", "I'll", "we'll", "plan to", "going to", "should", "will", "次は", "予定", "これから", or handing work to a person; a future action counts even when it names a different known task. BUT do not invent one: if the update only describes past/current work or is vague about the future, leave next_steps []. A risk's mitigation is not a next_step.
    * Each next_step: {{"description": str, "owner": str or null, "due_date": str or null}}. Normalize explicit calendar dates to ISO YYYY-MM-DD; leave vague ones ("Friday", "金曜日") as written.
- "owners" lists only people whose name LITERALLY appears in this update as doing or receiving work, including the person who receives handed-off work ("hand to Neeraj"/"ニーラジさんに渡す"/"Xに依頼" -> that person). Match to the known-people spelling (katakana maps to English, e.g. ニーラジ -> Neeraj). If no person is named, "owners" MUST be []. Never add someone because they are on the known-people list or normally own the task.
- "period" is an explicit reporting period if stated (e.g. "Week of June 8"), else null.
- "confidence" is your 0.0-1.0 confidence that the extraction is correct. Be low when the update is vague.
- Keep blocker/risk/next_step descriptions in the update's original language.

Return ONLY the JSON object, no prose."""


def _ollama_chat(text, world, model, base_url):
    payload = {
        "model": model,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": _system_prompt(world)},
            {"role": "user", "content": text},
        ],
    }
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ExtractorError(
            f"Cannot reach Ollama at {base_url} ({e}). Is `ollama serve` running and the model pulled?"
        ) from e
    content = body.get("message", {}).get("content", "")
    if not content:
        raise ExtractorError("Ollama returned an empty response.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ExtractorError(f"Model did not return valid JSON: {content[:200]}") from e


def _coerce(raw, world):
    """Normalize the model's JSON into the exact draft shape, dropping junk."""
    out = dict(EMPTY_DRAFT)
    known_projects = {p["name"] for p in world.get("projects", [])}
    known_tasks = {t for p in world.get("projects", []) for t in p.get("tasks", [])}
    known_people = set(world.get("people", []))

    project = raw.get("project")
    out["project"] = project if project in known_projects else "unknown"
    task = raw.get("task")
    out["task"] = task if task in known_tasks else None

    status = raw.get("status")
    out["status"] = status if status in STATUSES else None

    pct = raw.get("progress_pct")
    if isinstance(pct, (int, float)) and 0 <= pct <= 100:
        out["progress_pct"] = int(pct)

    out["blockers"] = [
        {
            "description": b.get("description", ""),
            "severity": b.get("severity") if b.get("severity") in SEVERITIES else None,
            "owner": b.get("owner"),
            "status": "resolved" if b.get("status") == "resolved" else "open",
        }
        for b in raw.get("blockers", []) or []
        if isinstance(b, dict) and b.get("description")
    ]
    out["risks"] = [
        {
            "description": r.get("description", ""),
            "likelihood": r.get("likelihood"),
            "impact": r.get("impact"),
            "mitigation": r.get("mitigation"),
            "owner": r.get("owner"),
        }
        for r in raw.get("risks", []) or []
        if isinstance(r, dict) and r.get("description")
    ]
    out["next_steps"] = [
        {
            "description": n.get("description", ""),
            "owner": n.get("owner"),
            "due_date": n.get("due_date"),
        }
        for n in raw.get("next_steps", []) or []
        if isinstance(n, dict) and n.get("description")
    ]
    out["owners"] = [o for o in raw.get("owners", []) or [] if o in known_people]

    out["period"] = raw.get("period") or None
    conf = raw.get("confidence")
    out["confidence"] = float(conf) if isinstance(conf, (int, float)) else 0.0
    return out


def extract(text, world, model=None, language="en"):
    """Extract a structured draft from `text`, grounded in `world`.

    Returns a dict matching the eval `expected` schema plus a `confidence` float.
    Raises ExtractorError if the local model is unreachable or returns bad output.
    `language` is accepted for parity with the API and future routing; the prompt
    handles EN/JA/code-switching without needing it.
    """
    if not text or not text.strip():
        return dict(EMPTY_DRAFT)
    raw = _ollama_chat(text, world, model or DEFAULT_MODEL, OLLAMA_URL)
    return _coerce(raw, world)
