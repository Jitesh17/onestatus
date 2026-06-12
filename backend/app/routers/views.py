"""Saved dashboard views (week 6): name a view-config and recall it later.

Views are stamped with their creator. Deleting is allowed for the creator or
for manager and up; views with no creator (saved before auth existed) count
as shared, so only manager and up may remove them.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/views", tags=["views"])


@router.get("", response_model=list[schemas.SavedViewOut])
def list_views(db: Session = Depends(get_db)):
    return [crud.view_to_dict(v) for v in crud.list_views(db)]


@router.post("", response_model=schemas.SavedViewOut, status_code=201)
def create_view(
    data: schemas.SavedViewIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    obj = crud.create_view(db, data.name, data.config.model_dump(), created_by=user.id)
    return crud.view_to_dict(obj)


@router.delete("/{view_id}", status_code=204)
def delete_view(
    view_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    view = db.get(models.SavedView, view_id)
    if view is None:
        raise HTTPException(status_code=404, detail="View not found")
    is_manager_up = models.ROLE_ORDER[user.role] >= models.ROLE_ORDER["manager"]
    if view.created_by != user.id and not is_manager_up:
        raise HTTPException(status_code=403, detail="Only the creator or a manager can delete this view")
    crud.delete_view(db, view_id)
