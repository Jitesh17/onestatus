"""Provider dispatch tests for app/llm.py: each provider builds the right HTTP
request (URL, headers, payload), parses its response shape, and maps failures
to ExtractorError. urllib.request.urlopen is patched, so nothing is contacted.
"""
import io
import json
import urllib.error

import pytest
from unittest.mock import patch

from app import llm
from app.config import settings
from app.llm import ExtractorError, llm_json


@pytest.fixture(autouse=True)
def _fresh_settings():
    """Each test starts from env defaults and leaks nothing to the next."""
    settings.reload_from_env()
    yield
    settings.reload_from_env()


class FakeResponse(io.BytesIO):
    """Minimal context-manager stand-in for the urlopen response object."""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _capture(response_body):
    """Return (urlopen_mock, captured) where captured collects each Request."""
    captured = []

    def fake_urlopen(req, timeout=None):
        captured.append({"req": req, "timeout": timeout,
                         "payload": json.loads(req.data.decode("utf-8"))})
        return FakeResponse(json.dumps(response_body).encode("utf-8"))

    return fake_urlopen, captured


OLLAMA_BODY = {"message": {"content": json.dumps({"project": "X"})}}
OPENAI_BODY = {"choices": [{"message": {"content": json.dumps({"project": "X"})}}]}
ANTHROPIC_BODY = {"content": [{"type": "text", "text": json.dumps({"project": "X"})}]}


# ---------- ollama ----------

def test_ollama_request_shape():
    fake, captured = _capture(OLLAMA_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        out = llm_json("sys", "user text")
    assert out == {"project": "X"}
    call = captured[0]
    assert call["req"].full_url == f"{settings.ollama_url}/api/chat"
    assert call["payload"]["model"] == settings.llm_model
    assert call["payload"]["format"] == "json"
    assert call["payload"]["stream"] is False
    assert call["payload"]["options"] == {"temperature": settings.llm_temperature}
    assert call["payload"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user text"},
    ]
    assert call["timeout"] == settings.llm_timeout


def test_ollama_model_override_wins():
    fake, captured = _capture(OLLAMA_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        llm_json("sys", "u", model="llama3.2:3b")
    assert captured[0]["payload"]["model"] == "llama3.2:3b"


def test_ollama_unreachable_mentions_ollama_serve():
    def fail(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    with patch.object(llm.urllib.request, "urlopen", fail):
        with pytest.raises(ExtractorError) as e:
            llm_json("sys", "u")
    assert "ollama serve" in str(e.value)


# ---------- openai-compatible ----------

def test_openai_request_shape_and_bearer():
    settings.apply_overrides({"llm_provider": "openai",
                              "llm_model": "gpt-4o-mini",
                              "llm_api_key": "sk-test",
                              "llm_temperature": 0.3})
    fake, captured = _capture(OPENAI_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        out = llm_json("sys", "u")
    assert out == {"project": "X"}
    call = captured[0]
    assert call["req"].full_url == "https://api.openai.com/v1/chat/completions"
    assert call["req"].get_header("Authorization") == "Bearer sk-test"
    assert call["payload"]["model"] == "gpt-4o-mini"
    assert call["payload"]["temperature"] == 0.3
    assert call["payload"]["response_format"] == {"type": "json_object"}


def test_openai_base_url_v1_suffix_not_doubled():
    """A base URL pasted with /v1 already on it must not become /v1/v1/..."""
    settings.apply_overrides({"llm_provider": "openai",
                              "llm_base_url": "http://gpu-box:8000/v1"})
    fake, captured = _capture(OPENAI_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        llm_json("sys", "u")
    assert captured[0]["req"].full_url == "http://gpu-box:8000/v1/chat/completions"


def test_openai_no_key_no_auth_header():
    settings.apply_overrides({"llm_provider": "openai",
                              "llm_base_url": "http://localhost:8000"})
    fake, captured = _capture(OPENAI_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        llm_json("sys", "u")
    assert captured[0]["req"].get_header("Authorization") is None


def test_openai_http_error_maps_to_extractor_error():
    settings.apply_overrides({"llm_provider": "openai", "llm_api_key": "bad"})

    def fail(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"error": "invalid key"}'))

    with patch.object(llm.urllib.request, "urlopen", fail):
        with pytest.raises(ExtractorError) as e:
            llm_json("sys", "u")
    assert "HTTP 401" in str(e.value)
    assert "invalid key" in str(e.value)


# ---------- anthropic ----------

def test_anthropic_request_shape():
    settings.apply_overrides({"llm_provider": "anthropic",
                              "llm_model": "claude-haiku-4-5-20251001",
                              "llm_api_key": "sk-ant-test"})
    fake, captured = _capture(ANTHROPIC_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        out = llm_json("sys", "u")
    assert out == {"project": "X"}
    call = captured[0]
    assert call["req"].full_url == "https://api.anthropic.com/v1/messages"
    assert call["req"].get_header("X-api-key") == "sk-ant-test"
    assert call["req"].get_header("Anthropic-version") == "2023-06-01"
    assert call["payload"]["system"] == "sys"
    assert call["payload"]["max_tokens"] == 2048
    assert call["payload"]["messages"] == [{"role": "user", "content": "u"}]


def test_anthropic_prose_wrapped_json_brace_slice():
    """No JSON mode on the Anthropic API: tolerate a prose preamble."""
    settings.apply_overrides({"llm_provider": "anthropic", "llm_api_key": "k"})
    body = {"content": [{"type": "text",
                         "text": 'Here is the JSON:\n{"project": "X"}\nDone.'}]}
    fake, _ = _capture(body)
    with patch.object(llm.urllib.request, "urlopen", fake):
        assert llm_json("sys", "u") == {"project": "X"}


# ---------- shared behavior ----------

def test_unknown_provider_raises():
    settings.apply_overrides({"llm_provider": "ollama"})
    settings.llm_provider = "watsonx"
    with pytest.raises(ExtractorError) as e:
        llm_json("sys", "u")
    assert "watsonx" in str(e.value)


def test_empty_content_raises():
    fake, _ = _capture({"message": {"content": ""}})
    with patch.object(llm.urllib.request, "urlopen", fake):
        with pytest.raises(ExtractorError) as e:
            llm_json("sys", "u")
    assert "empty" in str(e.value).lower()


def test_garbage_content_raises():
    fake, _ = _capture({"message": {"content": "not json at all"}})
    with patch.object(llm.urllib.request, "urlopen", fake):
        with pytest.raises(ExtractorError) as e:
            llm_json("sys", "u")
    assert "valid JSON" in str(e.value)


def test_extractor_seam_still_delegates():
    """extractor.ollama_json is the patch seam the suite relies on; it must
    forward to llm_json so a provider switch applies to /extract too."""
    from app import extractor
    fake, captured = _capture(OLLAMA_BODY)
    with patch.object(llm.urllib.request, "urlopen", fake):
        out = extractor.ollama_json("sys", "u", model="qwen2.5:7b")
    assert out == {"project": "X"}
    assert captured[0]["payload"]["model"] == "qwen2.5:7b"
