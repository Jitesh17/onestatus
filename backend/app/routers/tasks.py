"""Task endpoints. Reading is any logged-in member (router include);
creating tasks is manager and up."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import auth, crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    return crud.list_tasks(db, project_id)


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(
    data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_manager),
):
    return crud.create_task(db, data)
