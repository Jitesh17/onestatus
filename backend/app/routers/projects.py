"""Project endpoints. Reading is any logged-in member (router include);
creating projects is manager and up."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import auth, crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return crud.list_projects(db)


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    data: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_manager),
):
    return crud.create_project(db, data)
