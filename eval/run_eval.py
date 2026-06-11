"""Run an extractor over the eval dataset and score it per field.

By default this calls the real local-model extractor (backend/app/extractor.py) against
the eval world. Pass --placeholder to run the empty-returning stub instead (useful when
Ollama is not available and you just want to see the scoring format).

Usage:
    python eval/run_eval.py                      # real extractor, default model
    python eval/run_eval.py --model qwen2.5:7b   # real extractor, explicit model
    python eval/run_eval.py --placeholder        # stub, no model needed
"""
import argparse, json, os, sys, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
# Make backend/app importable so the eval uses the exact production extractor.
sys.path.insert(0, os.path.join(HERE, os.pardir, "backend"))


def load_dataset():
    with open(os.path.join(HERE, "world.json"), encoding="utf-8") as f:
        world = json.load(f)
    rows = []
    with open(os.path.join(HERE, "updates_eval.jsonl"), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return world, rows


# ---------------------------------------------------------------------------
# Placeholder extractor. Returns empty structure so the harness runs end to end
# without a model. Kept for --placeholder smoke tests.
# ---------------------------------------------------------------------------
def placeholder_extract(text, world, model=None):
    return {"project": "unknown", "task": None, "status": None, "progress_pct": None,
            "blockers": [], "risks": [], "owners": [], "next_steps": [], "period": None}


# ---------------------------------------------------------------------------
# Real extractor: the same function the /extract endpoint uses, against the eval world.
# ---------------------------------------------------------------------------
def real_extract(text, world, model=None):
    from app.extractor import extract  # imported lazily so --placeholder needs no backend deps
    return extract(text, world, model=model)


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
    ap.add_argument("--model", default="qwen2.5:7b", help="local model name for the real extractor")
    ap.add_argument("--placeholder", action="store_true", help="use the empty-returning stub (no model needed)")
    args = ap.parse_args()

    world, rows = load_dataset()
    fields = ["project", "task", "status", "progress_pct", "blockers", "risks", "next_steps", "owners"]
    totals = {f: [] for f in fields}
    by_lang = {"en": {f: [] for f in fields}, "ja": {f: [] for f in fields}}

    extractor = placeholder_extract if args.placeholder else real_extract
    label = "PLACEHOLDER (returns empties)" if args.placeholder else args.model

    for i, ex in enumerate(rows, 1):
        try:
            pred = extractor(ex["input_text"], world, args.model)
        except Exception as e:  # most likely Ollama unreachable; fail clearly, not with a trace
            print(f"\nExtractor failed on {ex['id']} ({i}/{len(rows)}): {e}", file=sys.stderr)
            print("If using the real extractor, ensure `ollama serve` is running and "
                  f"`ollama pull {args.model}` has completed. Or run with --placeholder.", file=sys.stderr)
            raise SystemExit(1)
        if not args.placeholder:
            print(f"  scored {ex['id']} ({i}/{len(rows)})", file=sys.stderr)
        s = score_example(pred, ex["expected"])
        for f in fields:
            totals[f].append(s[f])
            by_lang[ex["language"]][f].append(s[f])

    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print(f"Model: {label}")
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
    if args.placeholder:
        print("\nNote: placeholder scores are near zero by design. Drop --placeholder to score the real model.")


if __name__ == "__main__":
    main()
