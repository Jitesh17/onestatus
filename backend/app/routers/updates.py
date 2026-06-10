"""Update endpoints. Week 1 is manual entry only; the AI extract/transcribe
endpoints land in weeks 2 to 4 and will post into this same create path."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("", response_model=list[schemas.UpdateOut])
def list_updates(db: Session = Depends(get_db)):
    return crud.list_updates(db)


@router.post("", response_model=schemas.UpdateOut, status_code=201)
def create_update(data: schemas.UpdateCreate, db: Session = Depends(get_db)):
    return crud.create_update(db, data)
