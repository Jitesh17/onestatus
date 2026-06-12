"""API tests for /dashboard, /dashboard/presets, /dashboard/apply, /dashboard/configure.

/dashboard/configure normally calls the local LLM; here the Ollama call is mocked so the
real prompt assembly, _coerce, and guards still run. One live smoke test is marked."""
from unittest.mock import patch

import pytest

from app import schemas
from app.extractor import ExtractorError
from .factories import make_project, make_task, make_update, make_person


def _ollama_up():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def test_dashboard_seeded_shape_validates(client, seeded):
    r = client.get("/dashboard")
    assert r.status_code == 200
    out = schemas.DashboardOut(**r.json())
    assert out.totals["projects"] == 3
    assert len(out.per_team) == 3 and len(out.per_person) == 6
    assert out.trends.progress and out.trends.blockers


def test_dashboard_empty_db_200(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert r.json()["totals"] == {"projects": 0, "tasks": 0, "updates": 0}


def test_presets_shape(client, db):
    make_person(db, "Neeraj", team="Display Systems")
    r = client.get("/dashboard/presets")
    assert r.status_code == 200
    body = r.json()
    assert body["teams"] == ["Display Systems"]
    assert len(body["presets"]) == 6
    needs_team = [p for p in body["presets"] if p["needs_team"]]
    assert len(needs_team) == 2
    for p in needs_team:
        assert "{team}" in (p["config"].get("team") or "") or "{team}" in p["nl_phrase"]


def test_apply_filters_dashboard(client, db):
    p1, p2 = make_project(db, "P1"), make_project(db, "P2")
    make_task(db, p1, title="A", status="blocked")
    make_task(db, p2, title="B", status="done")
    r = client.post("/dashboard/apply", json={"config": {"status": "blocked"}})
    assert r.status_code == 200
    body = r.json()
    assert body["dashboard"]["totals"]["tasks"] == 1
    assert body["config"]["status"] == "blocked"


def test_apply_empty_config_equals_get(client, db):
    p = make_project(db)
    t = make_task(db, p)
    make_update(db, t, blockers=[("stuck", None)])
    plain = client.get("/dashboard").json()
    applied = client.post("/dashboard/apply", json={"config": {}}).json()["dashboard"]
    assert applied == plain


def test_apply_old_shape_config_still_works(client, db):
    """Saved views from before team/person existed must keep applying."""
    make_project(db)
    old = {"project": None, "status": None, "severity": None, "sections": [],
           "hide": ["risks"], "sort": None, "limit": None, "summary": "old view"}
    r = client.post("/dashboard/apply", json={"config": old})
    assert r.status_code == 200
    assert r.json()["config"]["team"] is None


def test_configure_mocked_llm(client, db):
    make_project(db, "BRAVIA Panel Calibration")
    raw = {"project": "BRAVIA", "status": "blocked", "summary": "blocked in BRAVIA"}
    with patch("app.view_interpreter.ollama_json", return_value=raw):
        r = client.post("/dashboard/configure",
                        json={"request": "only blocked tasks in BRAVIA"})
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg["project"] == "BRAVIA Panel Calibration"
    assert cfg["status"] == "blocked"


def test_configure_ollama_down_503(client, db):
    make_project(db)
    with patch("app.view_interpreter.ollama_json",
               side_effect=ExtractorError("Cannot reach Ollama")):
        r = client.post("/dashboard/configure", json={"request": "show blockers"})
    assert r.status_code == 503
    assert "Ollama" in r.json()["detail"]


@pytest.mark.live
def test_configure_live_smoke(client, seeded):
    if not _ollama_up():
        pytest.skip("Ollama not running")
    r = client.post("/dashboard/configure",
                    json={"request": "only blocked tasks in BRAVIA"})
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg["project"] == "BRAVIA Panel Calibration"
    assert cfg["status"] == "blocked"
