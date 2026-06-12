"""Local speech-to-text via faster-whisper (week 4).

Turns an uploaded audio clip into transcript text that then flows through the same
text pipeline (/extract -> confirmation editor -> /updates). Runs fully on-device:
CTranslate2 on CPU by default (WHISPER_DEVICE=cuda for a GPU box), no cloud, no
data leaving the machine.

The model is loaded lazily and kept as a module-level singleton so it is downloaded
and initialised once, not per request (the first call pulls ~1.5 GB for "medium").
All knobs are read from config.settings at call time, so the /settings API can
switch size/device live; reload() drops the singleton and the next request loads
the new configuration.
"""
import tempfile
import threading

from .config import settings

_model = None  # lazy singleton
_model_key = None  # (model, device, compute) the singleton was built with
_lock = threading.Lock()


class TranscriberError(RuntimeError):
    """Raised when audio cannot be loaded or transcribed."""


def reload():
    """Drop the cached model so the next request loads the current settings.

    Called by the settings router when a whisper field changes. A size change
    means the next /transcribe downloads the new model (up to ~3 GB for large).
    """
    global _model, _model_key
    with _lock:
        _model = None
        _model_key = None


def get_model():
    """Load the Whisper model once for the current settings."""
    global _model, _model_key
    key = (settings.whisper_model, settings.whisper_device, settings.whisper_compute)
    with _lock:
        if _model is None or _model_key != key:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:  # dependency not installed
                raise TranscriberError(
                    "faster-whisper is not installed. Run `pip install -r requirements.txt`."
                ) from e
            try:
                _model = WhisperModel(key[0], device=key[1], compute_type=key[2])
            except Exception as e:  # bad device (no CUDA), unknown size, etc.
                raise TranscriberError(f"Could not load whisper model {key}: {e}") from e
            _model_key = key
        return _model


def transcribe(audio_bytes: bytes, language: str | None = None):
    """Transcribe audio bytes to text.

    `language` (e.g. "en"/"ja") can be passed to skip auto-detection; None lets
    Whisper detect it. Returns {text, language, duration}. PyAV (bundled with
    faster-whisper) decodes wav/mp3/m4a/webm, so browser MediaRecorder blobs work.
    """
    if not audio_bytes:
        raise TranscriberError("Empty audio upload.")
    model = get_model()
    # faster-whisper reads a path or file-like; a temp file is the most format-robust.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        try:
            segments, info = model.transcribe(
                tmp.name,
                language=language or None,
                vad_filter=settings.whisper_vad,  # drop silence so short clips transcribe cleanly
                beam_size=settings.whisper_beam,
            )
            text = "".join(seg.text for seg in segments).strip()
        except Exception as e:  # decode failure, corrupt audio, etc.
            raise TranscriberError(f"Could not transcribe audio: {e}") from e
    return {
        "text": text,
        "language": getattr(info, "language", None) or language or "en",
        "duration": round(float(getattr(info, "duration", 0.0)), 2),
    }
