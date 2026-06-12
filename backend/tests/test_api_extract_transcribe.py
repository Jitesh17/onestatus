"""API tests for /extract and /transcribe.

/extract mocks app.extractor.ollama_json so the real _coerce + resolve_task_id +
project-backfill rule stay under test. /transcribe mocks the transcribe function
itself (the model is a 1.5 GB download); the [slow] test exercises the real model
on a generated WAV."""
import io
from unittest.mock import patch

import pytest

from app.extractor import ExtractorError
from app.transcriber import TranscriberError
from .factories import make_project, make_task


def _ollama_up():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


# ---------- /extract ----------
def test_extract_resolves_task_id(client, db):
    p = make_project(db, "Website Redesign")
    t = make_task(db, p, title="Checkout flow rework")
    raw = {"project": "Website Redesign", "task": "Checkout flow rework",
           "status": "in_progress", "progress_pct": 70, "confidence": 0.9}
    with patch("app.extractor.ollama_json", return_value=raw):
        r = client.post("/extract", json={"raw_text": "rig at 70 percent"})
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == t.id
    assert body["unknown_project"] is False and body["unknown_task"] is False
    assert body["progress_pct"] == 70


def test_extract_unknown_flags(client, db):
    make_project(db, "Website Redesign")
    raw = {"project": "Walkman Revival", "task": "Mystery task"}
    with patch("app.extractor.ollama_json", return_value=raw):
        r = client.post("/extract", json={"raw_text": "something unrelated"})
    body = r.json()
    assert body["project"] == "unknown"
    assert body["unknown_project"] is True
    # the coercer drops a task not in the known world, so unknown_task stays False
    assert body["task"] is None and body["unknown_task"] is False


def test_extract_project_backfilled_from_matched_task(client, db):
    p = make_project(db, "Data Pipeline Migration")
    make_task(db, p, title="ETL cutover module")
    raw = {"project": "unknown", "task": "ETL cutover module", "status": "blocked"}
    with patch("app.extractor.ollama_json", return_value=raw):
        r = client.post("/extract", json={"raw_text": "speaker separation is stuck"})
    body = r.json()
    assert body["project"] == "Data Pipeline Migration"
    assert body["unknown_project"] is False


def test_extract_coerces_junk(client, db):
    make_project(db, "P")
    raw = {"project": 42, "task": ["list"], "status": "vibing", "progress_pct": 250,
           "blockers": [{"no_description": True}, "not a dict"],
           "owners": ["Ghost Person"], "confidence": "high"}
    with patch("app.extractor.ollama_json", return_value=raw):
        r = client.post("/extract", json={"raw_text": "gibberish"})
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "unknown" and body["task"] is None
    assert body["status"] is None and body["progress_pct"] is None
    assert body["blockers"] == [] and body["owners"] == []
    assert body["confidence"] == 0.0


def test_extract_ollama_down_503(client, db):
    make_project(db, "P")
    with patch("app.extractor.ollama_json",
               side_effect=ExtractorError("Cannot reach Ollama")):
        r = client.post("/extract", json={"raw_text": "anything"})
    assert r.status_code == 503


@pytest.mark.live
def test_extract_live_smoke(client, seeded):
    if not _ollama_up():
        pytest.skip("Ollama not running")
    r = client.post("/extract", json={
        "raw_text": "Checkout flow rework is about 70 percent done now."})
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "Website Redesign"
    assert body["task"] == "Checkout flow rework"
    assert body["progress_pct"] == 70


# ---------- /transcribe ----------
def test_transcribe_missing_file_422(client):
    assert client.post("/transcribe").status_code == 422


def test_transcribe_empty_file_503_without_model(client):
    # transcriber raises "Empty audio upload" before any model load
    r = client.post("/transcribe", files={"file": ("a.wav", b"", "audio/wav")})
    assert r.status_code == 503
    assert "Empty" in r.json()["detail"]


def test_transcribe_mocked_success(client):
    fake = {"text": "hello world", "language": "en", "duration": 1.5}
    with patch("app.routers.transcribe.transcribe", return_value=fake):
        r = client.post("/transcribe",
                        files={"file": ("a.webm", b"fake-bytes", "audio/webm")},
                        data={"language": "en"})
    assert r.status_code == 200
    assert r.json() == fake


def test_transcribe_error_maps_to_503(client):
    with patch("app.routers.transcribe.transcribe",
               side_effect=TranscriberError("Could not transcribe audio")):
        r = client.post("/transcribe", files={"file": ("a.wav", b"xx", "audio/wav")})
    assert r.status_code == 503


@pytest.mark.slow
def test_transcribe_speechless_audio_clean_503(client):
    """A pure tone has no speech: the VAD drops everything and the endpoint must turn
    the internal failure into a clean 503, not a crash. Loads the real model."""
    import math
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 16000)))
            for i in range(16000))
        w.writeframes(frames)
    r = client.post("/transcribe",
                    files={"file": ("beep.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 503
    assert "transcribe" in r.json()["detail"].lower()


@pytest.mark.slow
def test_transcribe_real_model_spoken_clip(client, tmp_path):
    """End-to-end through the real faster-whisper model on synthesized speech
    (macOS `say`); skipped where no offline speech synthesizer exists."""
    import shutil
    import subprocess

    if not shutil.which("say"):
        pytest.skip("no offline speech synthesizer on this machine")
    clip = tmp_path / "clip.aiff"
    subprocess.run(["say", "-o", str(clip), "The test rig is seventy percent done."],
                   check=True)
    r = client.post("/transcribe",
                    files={"file": ("clip.aiff", clip.read_bytes(), "audio/aiff")})
    assert r.status_code == 200
    body = r.json()
    assert body["duration"] > 0
    assert "seventy" in body["text"].lower() or "70" in body["text"]
