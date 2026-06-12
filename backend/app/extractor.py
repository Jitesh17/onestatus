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
import difflib
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

# JA spellings of the known roster, so the literal-presence owner guard works on
# Japanese text (the prompt maps katakana -> English, e.g. ニーラジ -> Neeraj).
NAME_ALIASES = {
    "Jitesh": ["ジテッシュ"],
    "Neeraj": ["ニーラジ"],
    "Abhishake": ["アビシェイク", "アビシェーク"],
    "Shivam": ["シヴァム", "シバム"],
    "Tanaka-san": ["田中", "タナカ", "Tanaka"],
    "Sato-san": ["佐藤", "サトウ", "Sato"],
}


def _named_in_text(name, text):
    """True if the person's name (EN or a known JA spelling) appears in the text."""
    if not name or not text:
        return False
    if name.lower() in text.lower():
        return True
    return any(a in text for a in NAME_ALIASES.get(name, []))


class ExtractorError(RuntimeError):
    """Raised when the local model is unreachable or returns unusable output."""


def fuzzy_match(value, candidates, cutoff=0.8):
    """Map a near-miss model spelling to a known name, or None.

    Rescues outputs like "_calibration_dataset_prep" -> "Calibration dataset prep"
    instead of dropping a clearly-intended match. Exact members of `candidates`
    should be checked by the caller first; this only handles the near-misses.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    norm = value.strip().strip("_").replace("_", " ").lower()
    by_norm = {c.lower(): c for c in candidates}
    if norm in by_norm:
        return by_norm[norm]
    close = difflib.get_close_matches(norm, list(by_norm), n=1, cutoff=cutoff)
    return by_norm[close[0]] if close else None


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
- "task" is the task the update is primarily reporting progress on. If the update opens with a known task name ("X is stuck", "X is around 45 percent", "Xの件ですが"), that X is the task. A task mentioned only as something to do NEXT belongs in next_steps, not in "task". (e.g. "X is done, starting Y next" -> task is X, and Y is a next_step.)
- If the update reports on TWO separate tasks ("double update: X ... separately, Y ..."), extract the FIRST one as the task and report only ITS status/progress/blockers; do not attach the second task's details.
- If the update refers to a project NOT in the list, set "project" to "unknown" and "task" to null. Do not force a match.
- Do not invent facts. But DO infer status and capture next steps from how the update is phrased (see below) - those are stated, just not labeled.
- "status" is one of {STATUSES} or null. Infer it:
    * any update that describes ongoing work or reports any progress is "in_progress", even if it never says so ("looked into X", "got the pipeline running", "Shivam is taking over") -> in_progress;
    * "done"/"completed"/"finished"/"signed off"/"完了"/"完了し" -> done;
    * "blocked"/"stuck"/"waiting on"/"ブロック" -> blocked;
    * if the update reports a CURRENT blocker anywhere, status is "blocked" even when the work is described as basically/mostly done ("基本的にできたけど、GPUが足りなくて..." -> blocked, not done);
    * use null ONLY when the update gives no signal of any activity at all.
- "progress_pct" is an integer 0-100 or null. "done" implies 100.
- A blocker is something CURRENTLY stopping or slowing the work (no approval, expired license, server booked). A risk is something that MIGHT happen later (monsoon may delay, approval may slip). Never put a risk, a mitigation, or a next step into "blockers".
    * Each blocker: {{"description": str, "severity": one of {SEVERITIES} or null, "owner": str or null, "status": "open" or "resolved"}}.
- A risk is a possible future problem; keep its backup plan in the risk's "mitigation", NOT in next_steps.
    * Each risk: {{"description": str, "likelihood": str or null, "impact": str or null, "mitigation": str or null, "owner": str or null}}.
- next_steps: the actions the update actually proposes doing next. Trigger phrases: "next", "then", "after that", "I'll", "we'll", "plan to", "going to", "should", "will", "次は", "予定", "これから", or handing work to a person; a future action counts even when it names a different known task. BUT do not invent one: if the update only describes past/current work or is vague about the future, leave next_steps []. A progress figure alone ("about half done") does NOT imply a "finish the rest" next_step. A risk's mitigation is not a next_step.
    * Each next_step: {{"description": str, "owner": str or null, "due_date": str or null}}. A compound action ("draft the test plan and send it to the reviewer") is ONE next_step (owner = the recipient when named), not two steps. Write the description in the SAME language the update is written in: an English update gets an English description. The description names the action AND the thing it applies to ("finish the remaining wiring"), never a bare verb phrase like "will be completed"; in Japanese, include the object noun, not the verb alone. Normalize explicit calendar dates to ISO YYYY-MM-DD; leave vague ones ("Friday", "金曜日") EXACTLY as written in the original language - NEVER invent a YYYY-MM-DD date that is not in the text.
- "owners" lists only people whose name LITERALLY appears in this update as doing or receiving work, including the person who receives handed-off work ("hand to Neeraj"/"ニーラジさんに渡す"/"Xに依頼" -> that person). Match to the known-people spelling (katakana maps to English, e.g. ニーラジ -> Neeraj). If no person is named, "owners" MUST be []. Never add someone because they are on the known-people list or normally own the task. Approval or sign-off coming from a place or group ("Tokyo", "legal", "the PMO") names NO owner. The same literal-name rule applies to the "owner" field inside blockers/risks/next_steps: leave it null unless that person's name appears in the update.
- "period" is an explicit reporting period if stated (e.g. "Week of June 8"), else null.
- "confidence" is your 0.0-1.0 confidence that the extraction is correct. Be low when the update is vague.
- Write blocker/risk/next_step descriptions in the SAME language the update is written in: an English update gets English descriptions, a Japanese update gets Japanese descriptions. Never translate in either direction. Each description is a complete phrase (what the problem/action is), not a sentence fragment.

Return ONLY the JSON object, no prose."""


def ollama_json(system_prompt, user_text, model=None, base_url=None):
    """Call the local Ollama chat API in JSON mode and return the parsed dict.

    Shared by the extractor and the week-6 view interpreter. Raises ExtractorError on a
    connection failure or unparseable output so callers can surface a clean 503.
    """
    base_url = base_url or OLLAMA_URL
    payload = {
        "model": model or DEFAULT_MODEL,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
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


def _ollama_chat(text, world, model, base_url):
    return ollama_json(_system_prompt(world), text, model=model, base_url=base_url)


def _coerce(raw, world, text=""):
    """Normalize the model's JSON into the exact draft shape, dropping junk."""
    out = dict(EMPTY_DRAFT)
    known_projects = {p["name"] for p in world.get("projects", [])}
    known_tasks = {t for p in world.get("projects", []) for t in p.get("tasks", [])}
    known_people = set(world.get("people", []))

    # Non-string values (the model occasionally emits a list or number here) would
    # blow up the set-membership tests below; treat them as absent.
    project = raw.get("project")
    if not isinstance(project, str):
        project = None
    out["project"] = project if project in known_projects else "unknown"
    task = raw.get("task")
    if not isinstance(task, str):
        task = None
    if task not in known_tasks:
        task = fuzzy_match(task, known_tasks)
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
    # Owners must be known people whose name LITERALLY appears in the update; the
    # model sometimes adds a task's usual owner anyway, so enforce it in code.
    out["owners"] = [
        o for o in raw.get("owners", []) or []
        if o in known_people and _named_in_text(o, text)
    ]
    # A handoff recipient often lands only on the next_step ("hand to Neeraj");
    # promote known people named there into the top-level owners list.
    for n in out["next_steps"]:
        o = n.get("owner")
        if o in known_people and _named_in_text(o, text) and o not in out["owners"]:
            out["owners"].append(o)

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
    return _coerce(raw, world, text=text)
