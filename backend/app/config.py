"""Runtime configuration: every model and tunable parameter in one place.

A single mutable Settings instance backs the whole app. Defaults come from env
vars at import; the /settings API can change the mutable fields live, and the
non-secret ones persist to the app_settings table so a container restart keeps
the chosen provider/model. The LLM API key is env-or-memory only: it is never
written to the database and never echoed back by the API.

Boot-time knobs (DATABASE_URL, CORS_ORIGINS, MAX_AUDIO_BYTES, MAX_TEXT_LEN) are
read where they are used because they bind at import and cannot change live.

Env:
  LLM_PROVIDER     ollama | openai | anthropic        (default ollama)
  OLLAMA_URL       Ollama base URL                    (default http://localhost:11434)
  LLM_MODEL        model name; falls back to legacy OLLAMA_MODEL (default qwen2.5:7b)
  LLM_API_KEY      cloud provider key (openai/anthropic)
  LLM_BASE_URL     openai-compatible base URL override (vLLM, Ollama /v1, proxies)
  LLM_TEMPERATURE  sampling temperature               (default 0, deterministic)
  LLM_TIMEOUT      seconds per LLM call               (default 120)
  WHISPER_MODEL    faster-whisper size                (default medium)
  WHISPER_DEVICE   cpu | cuda                         (default cpu)
  WHISPER_COMPUTE  ctranslate2 compute type           (default int8)
  WHISPER_BEAM     beam size                          (default 5)
  WHISPER_VAD      voice activity detection, 0/1      (default 1)
"""
import json
import os

LLM_PROVIDERS = ("ollama", "openai", "anthropic")
WHISPER_DEVICES = ("cpu", "cuda")
WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v2", "large-v3")

# Fields the /settings API may change at runtime. Everything here except
# llm_api_key also persists to the app_settings table.
MUTABLE_FIELDS = (
    "llm_provider", "ollama_url", "llm_model", "llm_api_key", "llm_base_url",
    "llm_temperature", "llm_timeout",
    "whisper_model", "whisper_device", "whisper_compute", "whisper_beam", "whisper_vad",
)
SECRET_FIELDS = ("llm_api_key",)


class Settings:
    def __init__(self):
        self.reload_from_env()

    def reload_from_env(self):
        self.llm_provider = os.getenv("LLM_PROVIDER", "ollama")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.llm_model = os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_base_url = os.getenv("LLM_BASE_URL", "")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
        self.llm_timeout = int(os.getenv("LLM_TIMEOUT", "120"))
        self.whisper_model = os.getenv("WHISPER_MODEL", "medium")
        self.whisper_device = os.getenv("WHISPER_DEVICE", "cpu")
        self.whisper_compute = os.getenv("WHISPER_COMPUTE", "int8")
        self.whisper_beam = int(os.getenv("WHISPER_BEAM", "5"))
        self.whisper_vad = os.getenv("WHISPER_VAD", "1") not in ("0", "false", "False")

    def apply_overrides(self, data):
        """Set mutable fields from a dict; unknown keys are ignored by the caller."""
        for key, value in data.items():
            if key in MUTABLE_FIELDS:
                setattr(self, key, value)

    def to_dict(self, include_secrets=False):
        out = {k: getattr(self, k) for k in MUTABLE_FIELDS}
        if not include_secrets:
            for k in SECRET_FIELDS:
                out.pop(k, None)
        return out

    # -- persistence (single JSON row; see models.AppSetting) ------------------

    def load_from_db(self, db):
        """Apply persisted non-secret overrides on top of env defaults."""
        from . import models
        row = db.get(models.AppSetting, 1)
        if row and row.data:
            try:
                self.apply_overrides(json.loads(row.data))
            except (ValueError, TypeError):
                pass  # a corrupt row must never block boot; env defaults stand

    def save_to_db(self, db):
        from . import models
        data = json.dumps(self.to_dict(include_secrets=False))
        row = db.get(models.AppSetting, 1)
        if row is None:
            row = models.AppSetting(id=1, data=data)
            db.add(row)
        else:
            row.data = data
        db.commit()


settings = Settings()
