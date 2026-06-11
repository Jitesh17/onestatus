"""Transcription endpoint (week 4): audio -> transcript text.

Local speech-to-text via faster-whisper. Returns the transcript so the frontend can
drop it into the confirmation editor and run the existing /extract -> /updates flow.
Persists nothing.
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import schemas
from ..transcriber import transcribe, TranscriberError

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.post("", response_model=schemas.TranscriptOut)
async def transcribe_audio(file: UploadFile = File(...), language: str | None = Form(default=None)):
    audio = await file.read()
    try:
        result = transcribe(audio, language=language)
    except TranscriberError as e:
        # 503: the speech model is unavailable or the audio could not be decoded.
        raise HTTPException(status_code=503, detail=str(e)) from e
    return schemas.TranscriptOut(**result)
