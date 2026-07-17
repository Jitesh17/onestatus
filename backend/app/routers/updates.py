"""Update endpoints. Week 1 is manual entry only; the AI extract/transcribe
endpoints land in weeks 2 to 4 and will post into this same create path."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import auth, crud, llm, models, schemas
from ..database import get_db

router = APIRouter(prefix="/updates", tags=["updates"])

# On-demand translation (review sprint): nothing is persisted; the original text is
# the record, a translation is a reading aid. Uses whichever provider is configured,
# same as extraction, so local-only deployments stay local.
_TRANSLATE_PROMPT = """You translate one workplace status update into {target}.
Keep person names, project names, task names, numbers, percentages, and dates exactly
as written. Do not add, drop, or summarize anything.
Return ONLY a JSON object: {{"translation": "<the translated text>"}}"""


@router.get("", response_model=list[schemas.UpdateOut])
def list_updates(db: Session = Depends(get_db)):
    return crud.list_updates(db)


@router.post("", response_model=schemas.UpdateOut, status_code=201)
def create_update(
    data: schemas.UpdateCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    # The author column stays free text (the aggregation key), but the server
    # decides its value: members always post as themselves; manager and admin
    # may submit on someone's behalf via the author field.
    if models.ROLE_ORDER[user.role] < models.ROLE_ORDER["manager"] or not data.author:
        data.author = auth.author_name(user)
    return crud.create_update(db, data)


@router.post("/{update_id}/translate", response_model=schemas.TranslationOut)
def translate_update(update_id: int, data: schemas.TranslateRequest, db: Session = Depends(get_db)):
    upd = db.get(models.Update, update_id)
    if upd is None or not (upd.raw_text or "").strip():
        raise HTTPException(status_code=404, detail="Update not found or has no text.")
    target = "Japanese" if data.target == "ja" else "English"
    try:
        out = llm.llm_json(_TRANSLATE_PROMPT.format(target=target), upd.raw_text)
    except llm.ExtractorError as e:
        raise HTTPException(status_code=503, detail=str(e))
    text = str(out.get("translation") or "").strip()
    if not text:
        raise HTTPException(status_code=503, detail="The model returned an empty translation.")
    return {"update_id": update_id, "target": data.target, "text": text}
