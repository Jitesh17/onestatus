"""Local speech-to-text via faster-whisper (week 4).

Turns an uploaded audio clip into transcript text that then flows through the same
text pipeline (/extract -> confirmation editor -> /updates). Runs fully on-device:
CTranslate2 on CPU, no cloud, no data leaving the machine.

The model is loaded lazily and kept as a module-level singleton so it is downloaded
and initialised once, not per request (the first call pulls ~1.5 GB for "medium").

Env:
  WHISPER_MODEL    faster-whisper model size/name (default "medium")
  WHISPER_COMPUTE  compute type (default "int8"; CPU-friendly)
"""
import os
import tempfile

MODEL_NAME = os.getenv("WHISPER_MODEL", "medium")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "int8")

_model = None  # lazy singleton


class TranscriberError(RuntimeError):
    """Raised when audio cannot be loaded or transcribed."""


def get_model():
    """Load the Whisper model once. First call downloads it (~1.5 GB for medium)."""
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:  # dependency not installed
            raise TranscriberError(
                "faster-whisper is not installed. Run `pip install -r requirements.txt`."
            ) from e
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TYPE)
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
                vad_filter=True,  # drop silence so short clips transcribe cleanly
                beam_size=5,
            )
            text = "".join(seg.text for seg in segments).strip()
        except Exception as e:  # decode failure, corrupt audio, etc.
            raise TranscriberError(f"Could not transcribe audio: {e}") from e
    return {
        "text": text,
        "language": getattr(info, "language", None) or language or "en",
        "duration": round(float(getattr(info, "duration", 0.0)), 2),
    }
