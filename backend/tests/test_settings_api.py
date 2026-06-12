"""Settings API tests: read, partial update, persistence, secrets handling,
model discovery. The conftest autouse reset puts the singleton back to env
defaults before every test.
"""
import io
import json
import urllib.error

from unittest.mock import patch

from app import models
from app.config import settings


def test_get_settings_defaults(client):
    body = client.get("/settings").json()
    assert body["llm_provider"] == "ollama"
    assert body["llm_model"] == settings.llm_model
    assert body["whisper_model"] == "medium"
    assert body["api_key_set"] is False
    assert "llm_api_key" not in body


def test_put_settings_partial_update(client):
    r = client.put("/settings", json={"llm_model": "llama3.2:3b"})
    assert r.status_code == 200
    assert r.json()["llm_model"] == "llama3.2:3b"
    # untouched fields keep their values
    assert r.json()["llm_provider"] == "ollama"
    assert settings.llm_model == "llama3.2:3b"


def test_put_settings_persists_non_secrets(client, db):
    client.put("/settings", json={"llm_provider": "openai",
                                  "llm_model": "gpt-4o-mini",
                                  "llm_api_key": "sk-secret"})
    row = db.get(models.AppSetting, 1)
    assert row is not None
    saved = json.loads(row.data)
    assert saved["llm_provider"] == "openai"
    assert saved["llm_model"] == "gpt-4o-mini"
    # the key must never reach the database
    assert "llm_api_key" not in saved
    assert "sk-secret" not in row.data


def test_api_key_never_echoed(client):
    r = client.put("/settings", json={"llm_api_key": "sk-secret"})
    body = r.json()
    assert body["api_key_set"] is True
    assert "sk-secret" not in r.text
    # clearing the key flips the boolean back
    r2 = client.put("/settings", json={"llm_api_key": ""})
    assert r2.json()["api_key_set"] is False


def test_persisted_settings_survive_reload(client, db):
    client.put("/settings", json={"llm_model": "llama3.2:3b"})
    settings.reload_from_env()  # simulate a process restart
    assert settings.llm_model != "llama3.2:3b"
    settings.load_from_db(db)   # what main.py does on boot
    assert settings.llm_model == "llama3.2:3b"


def test_invalid_provider_422(client):
    r = client.put("/settings", json={"llm_provider": "watsonx"})
    assert r.status_code == 422
    assert settings.llm_provider == "ollama"  # nothing applied


def test_invalid_whisper_device_422(client):
    assert client.put("/settings", json={"whisper_device": "tpu"}).status_code == 422


def test_whisper_change_triggers_reload(client):
    with patch("app.routers.settings.transcriber") as mock_t:
        client.put("/settings", json={"whisper_model": "small"})
        mock_t.reload.assert_called_once()


def test_llm_change_does_not_reload_whisper(client):
    with patch("app.routers.settings.transcriber") as mock_t:
        client.put("/settings", json={"llm_model": "llama3.2:3b"})
        mock_t.reload.assert_not_called()


def test_models_endpoint_lists_ollama_tags(client):
    body = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:3b"}]}

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=None):
        assert url == f"{settings.ollama_url}/api/tags"
        return FakeResp(json.dumps(body).encode("utf-8"))

    with patch("app.routers.settings.urllib.request.urlopen", fake_urlopen):
        r = client.get("/settings/models")
    assert r.status_code == 200
    out = r.json()
    assert out["ollama_models"] == ["llama3.2:3b", "qwen2.5:7b"]  # sorted
    assert "medium" in out["whisper_sizes"]
    assert out["warning"] is None


def test_models_endpoint_ollama_down_is_warning_not_503(client):
    def fail(url, timeout=None):
        raise urllib.error.URLError("connection refused")

    with patch("app.routers.settings.urllib.request.urlopen", fail):
        r = client.get("/settings/models")
    assert r.status_code == 200
    out = r.json()
    assert out["ollama_models"] == []
    assert out["warning"]
    assert out["whisper_sizes"]  # whisper list still served for the panel
