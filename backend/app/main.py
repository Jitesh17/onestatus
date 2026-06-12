"""OneStatus API entrypoint (week 1).

Creates tables on startup, wires CORS for the local React dev server, and
mounts the project, task, and update routers.
"""
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from . import auth, config, models, migrate  # noqa: F401  (import registers models on Base before create_all)
from .create_admin import bootstrap_admin
from .routers import auth as auth_router
from .routers import projects, tasks, updates, extract, transcribe, dashboard, views, settings

# API_DOCS=0 disables Swagger/ReDoc/openapi.json in deployments; the dev loop keeps them.
_docs_on = os.getenv("API_DOCS", "1") in ("1", "true", "True")
app = FastAPI(
    title="OneStatus API",
    version="0.1.0",
    docs_url="/docs" if _docs_on else None,
    redoc_url="/redoc" if _docs_on else None,
    openapi_url="/openapi.json" if _docs_on else None,
)

# Week 1: create_all is enough. Move to Alembic migrations once the schema settles.
# create_all never ALTERs existing tables, so migrate.run adds any new nullable columns.
Base.metadata.create_all(bind=engine)
migrate.run(engine)

# Persisted settings (provider/model choices from the UI) override env defaults.
# First boot of the auth sprint: create the initial admin from ADMIN_PASSWORD
# (empty users table only; warns loudly when neither accounts nor env exist).
with SessionLocal() as _db:
    config.settings.load_from_db(_db)
    bootstrap_admin(_db)

# Docker first boot: seed the demo data when the flag is set and the DB is empty.
if os.getenv("SEED_ON_START", "0") in ("1", "true", "True"):
    with SessionLocal() as _db:
        if _db.query(models.Project).count() == 0:
            from . import seed_demo
            seed_demo.run()

# The React dev server runs on a different port, so allow it during development.
# In the docker deployment nginx serves the app same-origin and this is unused.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default-deny: every data router requires a logged-in user at include time, so a
# new endpoint cannot ship open by accident. /auth manages its own access (login is
# public, the rest authenticated) and stricter floors are raised per endpoint.
_member = [Depends(auth.require_member)]
app.include_router(auth_router.router)
app.include_router(projects.router, dependencies=_member)
app.include_router(tasks.router, dependencies=_member)
app.include_router(updates.router, dependencies=_member)
app.include_router(extract.router, dependencies=_member)
app.include_router(transcribe.router, dependencies=_member)
app.include_router(dashboard.router, dependencies=_member)
app.include_router(views.router, dependencies=_member)
app.include_router(settings.router, dependencies=_member)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
