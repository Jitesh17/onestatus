"""Runtime settings endpoints: read, change, and discover models.

Backs the frontend settings panel. Changes apply to the live config.settings
singleton immediately (the LLM and whisper layers read it at call time) and
the non-secret fields persist to the app_settings table so a restart keeps
them. The LLM API key is held in memory only: accepted on PUT, reported only
as the api_key_set boolean, never written to the database.
"""
import json
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, transcriber
from ..config import settings, WHISPER_SIZES
from ..database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

_WHISPER_FIELDS = ("whisper_model", "whisper_device", "whisper_compute")


def _settings_out():
    return schemas.SettingsOut(
        api_key_set=bool(settings.llm_api_key),
        **settings.to_dict(include_secrets=False),
    )


@router.get("", response_model=schemas.SettingsOut)
def get_settings():
    return _settings_out()


@router.put("", response_model=schemas.SettingsOut)
def put_settings(data: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    settings.apply_overrides(changes)
    settings.save_to_db(db)
    if any(f in changes for f in _WHISPER_FIELDS):
        # Drop the cached model; the next /transcribe loads the new one.
        transcriber.reload()
    return _settings_out()


@router.get("/models", response_model=schemas.ModelsOut)
def list_models():
    """Installed Ollama models + the fixed whisper size list.

    An unreachable Ollama is normal in cloud-API mode, so it is a warning in
    the body, not a 503: the panel still needs the whisper list and the cloud
    fields work without Ollama.
    """
    ollama_models, warning = [], None
    try:
        with urllib.request.urlopen(f"{settings.ollama_url}/api/tags", timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        ollama_models = sorted(m["name"] for m in body.get("models", []) if m.get("name"))
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as e:
        warning = f"Could not list Ollama models at {settings.ollama_url} ({e})."
    return schemas.ModelsOut(
        ollama_models=ollama_models,
        whisper_sizes=list(WHISPER_SIZES),
        warning=warning,
    )
