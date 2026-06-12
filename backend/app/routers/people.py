"""Org roster management. Reading is any logged-in member (the capture form and
dashboards need names); writing is admin, since team and department drive the
rollup reports. Deleting is blocked while a login account references the person,
so an author display name cannot silently fall back to a username.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/people", tags=["people"])


def _get_or_404(db: Session, person_id: int) -> models.Person:
    person = db.get(models.Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def _check_name_free(db: Session, name: str, exclude_id: int | None = None) -> None:
    q = db.query(models.Person).filter(models.Person.name == name)
    if exclude_id is not None:
        q = q.filter(models.Person.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409, detail="A person with this name already exists")


@router.get("", response_model=list[schemas.PersonOut])
def list_people(db: Session = Depends(get_db)):
    return db.query(models.Person).order_by(models.Person.name).all()


@router.post("", response_model=schemas.PersonOut, status_code=201)
def create_person(
    data: schemas.PersonIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    _check_name_free(db, data.name)
    person = models.Person(**data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.put("/{person_id}", response_model=schemas.PersonOut)
def update_person(
    person_id: int,
    data: schemas.PersonIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    person = _get_or_404(db, person_id)
    _check_name_free(db, data.name, exclude_id=person.id)
    for field, value in data.model_dump().items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=204)
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    person = _get_or_404(db, person_id)
    linked = db.query(models.User).filter(models.User.person_id == person.id).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail="A user account is linked to this person; unlink it first",
        )
    db.delete(person)
    db.commit()
