"""Test fixtures and database isolation.

app/database.py reads DATABASE_URL at import time and app/main.py runs create_all +
migrate at import time, so the env var MUST be set before anything under app.* is
imported. That is why this block sits at the top of conftest, before the app imports.
Every test run gets its own temp SQLite file; the dev onestatus.db is never opened.
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

_TMPDIR = tempfile.mkdtemp(prefix="onestatus-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMPDIR, 'test.db')}"
# Cheap bcrypt for tests: cost 4 instead of 12. Read at call time by app.auth.
os.environ["BCRYPT_ROUNDS"] = "4"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# Hard guard: if the env override ever stops working, fail loudly before any test
# can touch the developer database.
assert "onestatus.db" not in str(engine.url), f"tests bound to dev DB: {engine.url}"


@pytest.fixture(autouse=True)
def fresh_db():
    """Empty schema per test. drop_all + create_all is milliseconds on temp SQLite,
    and unlike transaction rollback it survives the commits crud does internally.
    The settings singleton is mutable at runtime (PUT /settings), so it is reset
    to env defaults too; without this a provider switch leaks between tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.config import settings as app_settings
    app_settings.reload_from_env()
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def relaxed_client():
    """Client that returns 500s instead of raising, for never-500 assertions."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def seeded(db):
    """Full demo dataset. Use only for shape/idempotency tests; unit tests build
    exactly what they need through factories instead."""
    from app import seed_demo
    seed_demo.run()
    yield db
