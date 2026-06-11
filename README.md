# Sony OneStatus

Voice-first bilingual project status platform, built for GearShift 2026.

Engineers speak or type status updates in English, Japanese, or a mix. A local language
model turns each update into a structured record (status, progress, blockers, risks, next
steps), a human confirms it on a review screen, and managers get a live dashboard they can
reshape with plain-language requests. Everything runs on one laptop: speech-to-text is
faster-whisper, extraction is qwen2.5:7b via Ollama, and nothing leaves the machine.
Extraction accuracy is 97% average per-field (EN 97%, JA 98%) on an internal 22-example
test set, so treat it as directional rather than a guarantee.

## What it does

- Capture by voice (record in the browser or upload a clip) or by text, in EN and JA
- Local LLM extraction into a draft: project, task, status, progress, blockers, risks,
  next steps, owners. Grounded in the known projects and people, so it links the right task
- Review screen: the AI proposes, a person edits and confirms, nothing saves unapproved
- Saving a confirmed update also updates the task itself, so the dashboard is always current
- Manager dashboard: delivery status, overall progress, open blockers and risks, per-project
  rollup, recent activity, upcoming next steps, and trend charts (progress over time, blocker
  burn-down) built from per-update history
- Natural-language dashboard control: "only blocked tasks in BRAVIA", "show the last 2 weeks",
  "top 3 blockers by severity", or the same in Japanese. Saved views recall a layout in one click
- Light and dark theme, remembered across sessions

## Stack

React (Vite) · FastAPI · SQLAlchemy · SQLite (Postgres optional) · Ollama qwen2.5:7b ·
faster-whisper medium

## Run it locally

Four pieces: a Python 3.11 venv, the Ollama model, the backend, the frontend.

1. Backend environment. The pinned dependencies have no Python 3.14 wheels, so use 3.11
   explicitly (plain `python -m venv` on a 3.14 default interpreter fails building psycopg2):

```bash
cd backend
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

2. The extraction model (about 4.7 GB):

```bash
ollama pull qwen2.5:7b
ollama serve
```

3. Backend. Run seed and uvicorn from `backend/`, not the repo root: the SQLite path is
   relative to the working directory and a wrong-cwd launch creates a second empty database.

```bash
cd backend
.venv/bin/python -m app.seed_demo
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`seed_demo` loads three demo projects with three weeks of backdated history so the trend
charts have a story. Use `app.seed` instead for a minimal dataset. API docs at
http://localhost:8000/docs

4. Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The first voice request downloads the faster-whisper model;
later requests take a few seconds. A scripted walkthrough lives in
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /health | liveness check |
| GET / POST | /projects | list / create projects |
| GET / POST | /tasks | list / create tasks (GET supports ?project_id=) |
| GET / POST | /updates | list / create status updates with nested items |
| POST | /transcribe | audio (multipart) to transcript via local faster-whisper; persists nothing |
| POST | /extract | free text to structured draft via local LLM; persists nothing |
| GET | /dashboard | manager KPIs, lists, and trend series aggregated from the data |
| POST | /dashboard/configure | natural-language request to view-config + filtered dashboard |
| POST | /dashboard/apply | apply an explicit or saved view-config |
| GET / POST / DELETE | /views | saved named view-configs |

## Extraction quality

22 labeled EN/JA cases, scored per field, multi-run averaged, deterministic at temperature 0:

```bash
backend/.venv/bin/python eval/run_eval.py --runs 1
```

Current headline: 0.97 average (EN 0.97, JA 0.98). Per field: project 1.00, task 0.95,
status 1.00, progress 1.00, blockers 0.91, risks 1.00, next_steps 0.91, owners 1.00.
The journey was 0.88 (week 2), 0.93 (week 3), 0.97 (hardening sprint: prompt rules plus
code guards such as only crediting owners whose names literally appear in the text).

We also compared 7B against 14B and kept 7B: it scored as well or better, tied on Japanese,
and ran about 40% faster on half the memory. Rationale in
[docs/status/MODEL_DECISION.md](docs/status/MODEL_DECISION.md).

## Project layout

```
backend/
  app/
    main.py             FastAPI app, CORS, table creation + column migration
    database.py         engine + session (SQLite default, Postgres via DATABASE_URL)
    migrate.py          additive column migration (create_all never ALTERs)
    models.py           SQLAlchemy ORM models
    schemas.py          Pydantic request/response shapes
    crud.py             database logic, dashboard aggregation, trend series
    extractor.py        local LLM extraction (Ollama)
    view_interpreter.py natural-language request to view-config
    seed.py             minimal demo data
    seed_demo.py        richer demo data + 3 weeks of backdated history
    routers/            projects, tasks, updates, extract, transcribe, dashboard, views
eval/                   labeled dataset + scoring harness
frontend/
  src/
    App.jsx             dashboard, capture, review screen, NL command bar
    api.js              API client
    main.jsx            entry + theme variables and styles
docker-compose.yml      optional Postgres path
```
