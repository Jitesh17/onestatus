# Sony OneStatus

Voice-First Bilingual Project Status and Dashboard Platform. GearShift 2026.

This is the **week 1** build: data model, FastAPI backend, and a plain manual-entry
UI. No AI yet. The goal of week 1 is to prove the full path works end to end
(type an update, save it to the database, read it back) before any AI is added.

## What works now

- PostgreSQL data model: projects, tasks, updates, and nested blockers, risks, next steps
- FastAPI backend with create and list endpoints for all three
- React UI to add projects, tasks, and status updates, and to view recent updates
- Bilingual fields (English/Japanese) on records, ready for the AI work in later weeks

## Stack

React (Vite) · FastAPI · SQLAlchemy · PostgreSQL · Docker

---

## Run it locally (fastest path, SQLite, no Docker)

The backend defaults to a local SQLite file, so you can run it with zero database setup.

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed            # optional: adds a little demo data
uvicorn app.main:app --reload --port 8000
```

API is now at http://localhost:8000 and interactive docs at http://localhost:8000/docs

**Frontend (in a second terminal):**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Run with Postgres (closer to production)

```bash
docker compose up --build
```

This starts Postgres and the backend together on port 8000. Then run the frontend
separately with `npm run dev` as above. To seed demo data into Postgres:

```bash
docker compose exec backend python -m app.seed
```

---

## Project layout

```
backend/
  app/
    main.py        FastAPI app, CORS, table creation
    database.py    engine + session (SQLite default, Postgres via DATABASE_URL)
    models.py      SQLAlchemy ORM models (the data model)
    schemas.py     Pydantic request/response shapes
    crud.py        all database logic
    seed.py        demo data
    routers/       projects, tasks, updates endpoints
frontend/
  src/
    App.jsx        forms + updates table
    api.js         API client
    main.jsx       entry + minimal styles
docker-compose.yml
```

## API endpoints (week 1)

| Method | Path | Purpose |
|---|---|---|
| GET | /health | liveness check |
| GET / POST | /projects | list / create projects |
| GET / POST | /tasks | list / create tasks (GET supports ?project_id=) |
| GET / POST | /updates | list / create status updates with nested items |
| POST | /extract | (week 2) text → structured draft via local LLM; persists nothing |
| POST | /transcribe | (week 4) audio (multipart) → transcript via local faster-whisper; persists nothing |
| GET | /dashboard | (week 5) fixed manager KPIs aggregated from the data |
| POST | /dashboard/configure | (week 6) natural-language command → view-config + filtered dashboard |
| POST | /dashboard/apply | (week 6) apply an explicit/saved view-config → filtered dashboard |
| GET / POST / DELETE | /views | (week 6) saved named view-configs |

## Coming next (per the build plan)

- Week 2: text update to structured records via local LLM, with the confirmation block editor
- Week 3: extraction quality check in English and Japanese, go/no-go on model size
- Week 4: voice input via faster-whisper feeding the same pipeline
- Week 5: manager dashboard with fixed KPIs
- Week 6: natural-language dashboard reconfiguration and saved views

The AI endpoints in week 2 onward will post into the existing `/updates` create path,
so this week's foundation does not get rewritten.
