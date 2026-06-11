"""Extraction endpoint (week 2): free-form text -> structured draft.

Returns a proposal for the confirmation block editor. Persists nothing; the human
edits the draft and saves it through the existing POST /updates path.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..extractor import extract, ExtractorError

router = APIRouter(prefix="/extract", tags=["extract"])


@router.post("", response_model=schemas.ExtractDraft)
def extract_update(data: schemas.ExtractRequest, db: Session = Depends(get_db)):
    world = crud.build_world(db)
    try:
        draft = extract(data.raw_text, world, model=data.model, language=data.language)
    except ExtractorError as e:
        # 503: the model backend is down or misbehaving, not a client error.
        raise HTTPException(status_code=503, detail=str(e)) from e

    task_id = crud.resolve_task_id(db, draft.get("project"), draft.get("task"))
    return schemas.ExtractDraft(
        project=draft.get("project") or "unknown",
        task=draft.get("task"),
        task_id=task_id,
        unknown_project=(draft.get("project") in (None, "unknown")),
        unknown_task=(draft.get("task") is not None and task_id is None),
        status=draft.get("status"),
        progress_pct=draft.get("progress_pct"),
        blockers=draft.get("blockers", []),
        risks=draft.get("risks", []),
        next_steps=draft.get("next_steps", []),
        owners=draft.get("owners", []),
        period=draft.get("period"),
        confidence=draft.get("confidence", 0.0),
    )
