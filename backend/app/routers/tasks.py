"""Task endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    return crud.list_tasks(db, project_id)


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    return crud.create_task(db, data)
