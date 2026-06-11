"""Sony OneStatus API entrypoint (week 1).

Creates tables on startup, wires CORS for the local React dev server, and
mounts the project, task, and update routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401  (import registers models on Base before create_all)
from .routers import projects, tasks, updates, extract, transcribe, dashboard

app = FastAPI(title="Sony OneStatus API", version="0.1.0")

# Week 1: create_all is enough. Move to Alembic migrations once the schema settles.
Base.metadata.create_all(bind=engine)

# The React dev server runs on a different port, so allow it during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(updates.router)
app.include_router(extract.router)
app.include_router(transcribe.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
