"""Run an extractor over the eval dataset and score it per field.

Today it uses a placeholder extractor so you can see the scoring output. In week 2,
replace `placeholder_extract` with a real call to the local model and pass --model.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --model qwen2.5:7b      # once the real extractor is wired
"""
import argparse, json, os, difflib

HERE = os.path.dirname(os.path.abspath(__file__))


def load_dataset():
    with open(os.path.join(HERE, "world.json"), encoding="utf-8") as f:
        world = json.load(f)
    rows = []
    with open(os.path.join(HERE, "updates_eval.jsonl"), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return world, rows


# ---------------------------------------------------------------------------
# Placeholder extractor. Returns empty structure so the harness runs end to end.
# Week 2: swap this for a function that calls the local LLM with the constrained
# JSON prompt and returns the same dict shape as `expected`.
# ---------------------------------------------------------------------------
def placeholder_extract(text, world, model=None):
    return {"project": "unknown", "task": None, "status": None, "progress_pct": None,
            "blockers": [], "risks": [], "owners": [], "next_steps": [], "period": None}


# ---------------------------------------------------------------------------
# Per-field scoring helpers.
# ---------------------------------------------------------------------------
def _norm(s):
    return (s or "").strip().lower()


def score_example(pred, exp):
    """Return a dict of field -> 1.0/0.0 (or fractional for list fields)."""
    s = {}
    s["project"] = 1.0 if _norm(pred.get("project")) == _norm(exp.get("project")) else 0.0
    s["task"] = 1.0 if _norm(pred.get("task")) == _norm(exp.get("task")) else 0.0
    s["status"] = 1.0 if _norm(pred.get("status")) == _norm(exp.get("status")) else 0.0

    ep, pp = exp.get("progress_pct"), pred.get("progress_pct")
    if ep is None:
        s["progress_pct"] = 1.0 if pp is None else 0.0
    else:
        s["progress_pct"] = 1.0 if (pp is not None and abs(pp - ep) <= 10) else 0.0

    s["blockers"] = _list_score(pred.get("blockers", []), exp.get("blockers", []))
    s["risks"] = _list_score(pred.get("risks", []), exp.get("risks", []))
    s["next_steps"] = _list_score(pred.get("next_steps", []), exp.get("next_steps", []))
    s["owners"] = _set_score(pred.get("owners", []), exp.get("owners", []))
    return s


def _desc_match(a, b):
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= 0.5


def _list_score(pred, exp):
    """Fraction of expected items matched by description overlap. Empty/empty = 1.0."""
    if not exp:
        return 1.0 if not pred else 0.0
    matched = 0
    for e in exp:
        if any(_desc_match(p.get("description", ""), e.get("description", "")) for p in pred):
            matched += 1
    return matched / len(exp)


def _set_score(pred, exp):
    if not exp:
        return 1.0 if not pred else 0.0
    ep, pp = set(exp), set(pred)
    return len(ep & pp) / len(ep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="local model name (used once the real extractor is wired)")
    args = ap.parse_args()

    world, rows = load_dataset()
    fields = ["project", "task", "status", "progress_pct", "blockers", "risks", "next_steps", "owners"]
    totals = {f: [] for f in fields}
    by_lang = {"en": {f: [] for f in fields}, "ja": {f: [] for f in fields}}

    for ex in rows:
        pred = placeholder_extract(ex["input_text"], world, args.model)
        s = score_example(pred, ex["expected"])
        for f in fields:
            totals[f].append(s[f])
            by_lang[ex["language"]][f].append(s[f])

    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print(f"Model: {args.model or 'PLACEHOLDER (returns empties)'}")
    print(f"Examples: {len(rows)}\n")
    print(f"{'field':<14}{'overall':>9}{'EN':>8}{'JA':>8}")
    print("-" * 39)
    for f in fields:
        print(f"{f:<14}{avg(totals[f]):>9.2f}{avg(by_lang['en'][f]):>8.2f}{avg(by_lang['ja'][f]):>8.2f}")
    overall = avg([v for f in fields for v in totals[f]])
    en = avg([v for f in fields for v in by_lang['en'][f]])
    ja = avg([v for f in fields for v in by_lang['ja'][f]])
    print("-" * 39)
    print(f"{'AVERAGE':<14}{overall:>9.2f}{en:>8.2f}{ja:>8.2f}")
    print("\nNote: placeholder scores are near zero by design. Real numbers appear once")
    print("the local-model extractor replaces placeholder_extract in week 2.")


if __name__ == "__main__":
    main()
