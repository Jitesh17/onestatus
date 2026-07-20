# OneStatus evaluation dataset

This is the labeled data we use to judge whether the local model extracts status
updates well enough, especially in Japanese. It is the basis for the week 3 go/no-go
decision on model size.

All data here is synthetic. No real project data is used, which keeps it safe to
work with anywhere during early development.

## Files

- `world.json` : the fake world the updates refer to. Projects, their tasks, and the
  list of people. The extractor uses this to match names instead of inventing them.
- `updates_eval.jsonl` : one labeled example per line. Each is a free-form update paired
  with the correct structured extraction.
- `build_dataset.py` : regenerates the two files above and validates the labels.
- `run_eval.py` : runs an extractor over the dataset and scores it (see below).

## Example shape

```json
{
  "id": "ex_002",
  "situation": "multiple blockers plus a risk",
  "language": "en",
  "source": "text",
  "input_text": "Design review pipeline is stuck...",
  "expected": {
    "project": "Website Redesign",
    "task": "Design review pipeline",
    "status": "blocked",
    "progress_pct": null,
    "blockers": [{"description": "...", "severity": "high", "owner": null}],
    "risks": [{"description": "...", "impact": "high", "mitigation": null}],
    "owners": [],
    "next_steps": [],
    "period": null
  },
  "notes": "what this example is testing"
}
```

`expected` follows the extraction schema in the architecture doc. Fields are `null` or
empty where the update does not state them. This matters: a good extractor should leave
them empty, not guess.

## Situations covered (22 examples, 15 EN / 7 JP)

The point is not volume, it is coverage of the cases that break extractors:

- Clean single-task updates with explicit progress (ex_001, ex_011)
- Multiple blockers with different severities, plus a separate risk (ex_002)
- Very terse updates (ex_003, ex_013)
- Rambling updates full of filler (ex_004)
- Owner detection from handoff phrases, including katakana names (ex_005, ex_014, ex_018)
- An unknown project that must not be force-matched (ex_006, ex_022)
- Two tasks packed into one update (ex_007)
- A previously blocking item now resolved (ex_008)
- A risk with a mitigation and no blocker (ex_009, ex_015)
- Low-information and vague updates where the model must return empties (ex_010, ex_022)
- Polite business Japanese (ex_012)
- Completed tasks in both languages (ex_019, ex_020)
- Explicit dates normalized to ISO and multiple owners (ex_018)
- An explicit reporting period, taking the latest progress value (ex_021)
- Code-switching between English and Japanese in both directions (ex_016, ex_017)

The code-switching and katakana-name cases are the bilingual-team reality and are the
ones most worth watching during the week 3 check.

## How to use it

Week 2: build the extraction endpoint, then run `run_eval.py` to see where it stands.
Week 3: run it again on the larger model if needed, compare scores, decide 7B vs 32B.

```bash
# from the repo root, with the backend env active
python eval/run_eval.py --model qwen2.5:7b
```

`run_eval.py` calls the real production extractor (`backend/app/extractor.py`) by default,
so `python eval/run_eval.py` scores the live local model. Pass `--placeholder` to run the
empty-returning stub instead (useful when Ollama is not available and you just want to see
the scoring output format).

## Scoring approach

We score per field, not all-or-nothing, because partial extraction is still useful:

- project, task, status: exact match (after name matching to the world)
- progress_pct: correct if within 10 points of expected (updates are fuzzy by nature)
- blockers, risks, next_steps: matched on overlap of description plus key attributes
- owners: set match against the world's people

The headline number is the per-field accuracy averaged across examples, reported
separately for English and Japanese so we can see the JP gap directly.

## Extending the dataset

Add cases to `build_dataset.py` using the `add(...)` helper, then rerun it. The script
validates every label against the world and the schema before writing, so a bad label
fails loudly instead of silently corrupting the golden data.
