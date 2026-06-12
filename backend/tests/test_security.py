"""Security-behavior tests: injection, payload abuse, validation bounds, CORS, limits.

Uses relaxed_client (raise_server_exceptions=False) so a 500 shows up as a failed
status assertion instead of a stack trace; "hostile input never 500s" is the contract."""
from unittest.mock import patch

from sqlalchemy import text

from app.database import engine
from app.routers.transcribe import MAX_AUDIO_BYTES
from app.schemas import MAX_TEXT_LEN
from .factories import make_project, make_task

SQLI = "'; DROP TABLE projects; --"
XSS = "<script>alert('x')</script><img src=x onerror=alert(1)>"


# ---------- injection ----------
def test_sqli_string_stored_literally(relaxed_client):
    r = relaxed_client.post("/projects", json={"name": SQLI})
    assert r.status_code in (200, 201)
    assert r.json()["name"] == SQLI
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "projects" in tables
    assert relaxed_client.get("/projects").json()[0]["name"] == SQLI


def test_sqli_in_query_param_rejected(relaxed_client):
    r = relaxed_client.get("/tasks", params={"project_id": SQLI})
    assert r.status_code == 422


def test_xss_payload_round_trips_raw_json(relaxed_client, db):
    p = make_project(db)
    t = make_task(db, p)
    r = relaxed_client.post("/updates", json={"task_id": t.id, "raw_text": XSS,
                                              "author": XSS})
    assert r.status_code in (200, 201)
    # JSON API: stored and returned verbatim, never reflected as HTML.
    assert r.json()["raw_text"] == XSS
    assert r.headers["content-type"].startswith("application/json")


def test_unicode_heavy_input_ok(relaxed_client, db):
    p = make_project(db)
    t = make_task(db, p)
    weird = "日本語🎌\u202e null\uffff mixed ブロッカー"
    r = relaxed_client.post("/updates", json={"task_id": t.id, "raw_text": weird})
    assert r.status_code in (200, 201)


# ---------- payload limits (the new caps) ----------
def test_extract_text_over_cap_422(relaxed_client):
    r = relaxed_client.post("/extract", json={"raw_text": "x" * (MAX_TEXT_LEN + 1)})
    assert r.status_code == 422


def test_extract_text_at_cap_passes_validation(relaxed_client, db):
    make_project(db)
    with patch("app.extractor.ollama_json", return_value={}):
        r = relaxed_client.post("/extract", json={"raw_text": "x" * MAX_TEXT_LEN})
    assert r.status_code == 200


def test_configure_text_over_cap_422(relaxed_client):
    r = relaxed_client.post("/dashboard/configure",
                            json={"request": "y" * (MAX_TEXT_LEN + 1)})
    assert r.status_code == 422


def test_update_text_over_cap_422(relaxed_client):
    r = relaxed_client.post("/updates", json={"raw_text": "z" * (MAX_TEXT_LEN + 1)})
    assert r.status_code == 422


def test_transcribe_oversized_upload_413(relaxed_client):
    big = b"0" * (MAX_AUDIO_BYTES + 1)
    r = relaxed_client.post("/transcribe", files={"file": ("big.wav", big, "audio/wav")})
    assert r.status_code == 413


def test_transcribe_under_cap_reaches_transcriber(relaxed_client):
    fake = {"text": "ok", "language": "en", "duration": 0.5}
    with patch("app.routers.transcribe.transcribe", return_value=fake) as mocked:
        r = relaxed_client.post("/transcribe",
                                files={"file": ("a.wav", b"small", "audio/wav")})
    assert r.status_code == 200
    mocked.assert_called_once()


# ---------- validation bounds ----------
def test_wrong_enum_422(relaxed_client, db):
    p = make_project(db)
    r = relaxed_client.post("/tasks", json={"project_id": p.id, "title": "T",
                                            "status": "exploded"})
    assert r.status_code == 422


def test_progress_pct_bounds_422(relaxed_client, db):
    p = make_project(db)
    for bad in (-1, 101):
        r = relaxed_client.post("/tasks", json={"project_id": p.id, "title": "T",
                                                "progress_pct": bad})
        assert r.status_code == 422


def test_hostile_limit_and_days_still_200(relaxed_client, db):
    make_project(db)
    for cfg in ({"limit": 10**9}, {"days": 10**6}, {"limit": -5, "days": -5}):
        r = relaxed_client.post("/dashboard/apply", json={"config": cfg})
        assert r.status_code == 200, cfg


def test_malformed_json_422(relaxed_client):
    r = relaxed_client.post("/projects", content=b"{not json",
                            headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_wrong_content_type_422(relaxed_client):
    r = relaxed_client.post("/projects", content=b"name=plain",
                            headers={"Content-Type": "text/plain"})
    assert r.status_code == 422


def test_unknown_route_404_wrong_method_405(relaxed_client):
    assert relaxed_client.get("/admin").status_code == 404
    assert relaxed_client.delete("/health").status_code == 405


def test_garbage_multipart_never_500(relaxed_client):
    r = relaxed_client.post("/transcribe", content=b"\x00\xff garbage",
                            headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code in (400, 422)


# ---------- CORS ----------
def test_cors_allowed_origin_echoed(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin_absent(client):
    r = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_preflight_ok(client):
    r = client.options("/dashboard/configure", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
