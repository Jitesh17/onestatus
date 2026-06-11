"""Saved dashboard views (week 6): name a view-config and recall it later."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/views", tags=["views"])


@router.get("", response_model=list[schemas.SavedViewOut])
def list_views(db: Session = Depends(get_db)):
    return [crud.view_to_dict(v) for v in crud.list_views(db)]


@router.post("", response_model=schemas.SavedViewOut, status_code=201)
def create_view(data: schemas.SavedViewIn, db: Session = Depends(get_db)):
    obj = crud.create_view(db, data.name, data.config.model_dump())
    return crud.view_to_dict(obj)


@router.delete("/{view_id}", status_code=204)
def delete_view(view_id: int, db: Session = Depends(get_db)):
    if not crud.delete_view(db, view_id):
        raise HTTPException(status_code=404, detail="View not found")
