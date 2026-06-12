"""Run an extractor over the eval dataset and score it per field.

By default this calls the real local-model extractor (backend/app/extractor.py) against
the eval world. Pass --placeholder to run the empty-returning stub instead (useful when
Ollama is not available and you just want to see the scoring format).

Usage:
    python eval/run_eval.py                          # real extractor, default model, 1 run
    python eval/run_eval.py --model qwen2.5:14b       # explicit model
    python eval/run_eval.py --runs 3                  # average 3 runs/example (smooths noise)
    python eval/run_eval.py --runs 3 --errors         # also list every field that scored < 1.0
    python eval/run_eval.py --placeholder             # stub, no model needed

Provider passthrough (compare local vs cloud as two invocations):
    python eval/run_eval.py --provider openai --model gpt-4o-mini --api-key sk-...
    python eval/run_eval.py --provider openai --base-url http://gpu-box:8000 --model ...
    python eval/run_eval.py --provider anthropic --model claude-haiku-4-5-20251001 --api-key sk-ant-...
"""
import argparse, json, os, sys, time, difflib

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


FIELDS = ["project", "task", "status", "progress_pct", "blockers", "risks", "next_steps", "owners"]


def _avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = _avg(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def _fmt_field(pred, exp, f):
    """Short, readable predicted-vs-expected for one field (used by --errors)."""
    def short(v):
        if isinstance(v, list):
            return "[" + "; ".join((i.get("description", "") if isinstance(i, dict) else str(i))[:40] for i in v) + "]"
        return str(v)
    return f"{f}: expected={short(exp.get(f))!r}  got={short(pred.get(f))!r}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b", help="model name for the chosen provider")
    ap.add_argument("--runs", type=int, default=1, help="extractions per example; per-field scores are averaged (smooths temp-0 noise)")
    ap.add_argument("--errors", action="store_true", help="after scoring, list every example/field that scored < 1.0 (uses the last run)")
    ap.add_argument("--placeholder", action="store_true", help="use the empty-returning stub (no model needed)")
    ap.add_argument("--provider", choices=["ollama", "openai", "anthropic"], default=None,
                    help="LLM provider (default: the LLM_PROVIDER env or ollama)")
    ap.add_argument("--base-url", default=None, help="openai-compatible base URL (vLLM, proxies)")
    ap.add_argument("--api-key", default=None, help="cloud provider API key (or set LLM_API_KEY)")
    ap.add_argument("--temperature", type=float, default=None, help="sampling temperature (default 0)")
    args = ap.parse_args()

    # Point the shared settings singleton at the requested provider before any
    # extraction; extractor -> llm_json reads these at call time.
    overrides = {k: v for k, v in {
        "llm_provider": args.provider, "llm_base_url": args.base_url,
        "llm_api_key": args.api_key, "llm_temperature": args.temperature,
    }.items() if v is not None}
    if overrides and not args.placeholder:
        from app.config import settings
        settings.apply_overrides(overrides)

    world, rows = load_dataset()
    totals = {f: [] for f in FIELDS}                                   # per-example mean scores
    by_lang = {"en": {f: [] for f in FIELDS}, "ja": {f: [] for f in FIELDS}}
    spread = {f: [] for f in FIELDS}                                   # per-example std across runs
    failures = []                                                     # (id, lang, [field-strings]) from last run

    extractor = placeholder_extract if args.placeholder else real_extract
    provider = args.provider or os.getenv("LLM_PROVIDER", "ollama")
    label = "PLACEHOLDER (returns empties)" if args.placeholder else f"{args.model} [{provider}]"
    started = time.time()

    for i, ex in enumerate(rows, 1):
        run_scores = {f: [] for f in FIELDS}
        last_pred = None
        for r in range(args.runs):
            try:
                pred = extractor(ex["input_text"], world, args.model)
            except Exception as e:  # most likely Ollama unreachable; fail clearly, not with a trace
                print(f"\nExtractor failed on {ex['id']} ({i}/{len(rows)}): {e}", file=sys.stderr)
                print("If using the real extractor, ensure `ollama serve` is running and "
                      f"`ollama pull {args.model}` has completed. Or run with --placeholder.", file=sys.stderr)
                raise SystemExit(1)
            last_pred = pred
            s = score_example(pred, ex["expected"])
            for f in FIELDS:
                run_scores[f].append(s[f])
        if not args.placeholder:
            print(f"  scored {ex['id']} ({i}/{len(rows)}) x{args.runs}", file=sys.stderr)
        for f in FIELDS:
            m = _avg(run_scores[f])
            totals[f].append(m)
            by_lang[ex["language"]][f].append(m)
            spread[f].append(_stdev(run_scores[f]))
        if args.errors and last_pred is not None:
            miss = [_fmt_field(last_pred, ex["expected"], f) for f in FIELDS
                    if score_example(last_pred, ex["expected"])[f] < 1.0]
            if miss:
                failures.append((ex["id"], ex["language"], miss))

    elapsed = time.time() - started

    print(f"Model: {label}")
    print(f"Examples: {len(rows)} | runs/example: {args.runs} | wall: {elapsed:.1f}s"
          f" ({elapsed / (len(rows) * args.runs):.2f}s/extraction)\n")
    print(f"{'field':<14}{'overall':>9}{'EN':>8}{'JA':>8}{'±sd':>8}")
    print("-" * 47)
    for f in FIELDS:
        print(f"{f:<14}{_avg(totals[f]):>9.2f}{_avg(by_lang['en'][f]):>8.2f}{_avg(by_lang['ja'][f]):>8.2f}{_avg(spread[f]):>8.2f}")
    overall = _avg([v for f in FIELDS for v in totals[f]])
    en = _avg([v for f in FIELDS for v in by_lang['en'][f]])
    ja = _avg([v for f in FIELDS for v in by_lang['ja'][f]])
    print("-" * 47)
    print(f"{'AVERAGE':<14}{overall:>9.2f}{en:>8.2f}{ja:>8.2f}")
    print("\n±sd is the mean per-example std across runs: the noise floor. 0.00 = fully stable.")
    if args.placeholder:
        print("Note: placeholder scores are near zero by design. Drop --placeholder to score the real model.")

    if args.errors:
        print(f"\n{'=' * 47}\nMisses (last run, fields scoring < 1.0):")
        for eid, lang, miss in failures:
            print(f"\n[{eid} · {lang}]")
            for m in miss:
                print(f"  {m}")
        if not failures:
            print("  none: every field scored 1.0 on the last run.")


if __name__ == "__main__":
    main()
