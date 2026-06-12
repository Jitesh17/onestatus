"""Login, session, and user administration endpoints.

POST /auth/login and the /health check are the only public routes; everything
else in the app sits behind the session cookie (enforcement lands in main.py
router includes). User CRUD is admin-only and guards the last active admin so
the office server cannot lock itself out from the UI; the CLI escape hatch is
`python -m app.create_admin`.
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _me_out(user: models.User) -> schemas.MeOut:
    return schemas.MeOut(
        id=user.id,
        username=user.username,
        role=user.role,
        person_id=user.person_id,
        author=auth.author_name(user),
    )


def _check_password_bytes(password: str) -> None:
    # Pydantic max_length counts characters; bcrypt's limit is 72 BYTES.
    if len(password.encode("utf-8")) > schemas.PASSWORD_MAX:
        raise HTTPException(status_code=422, detail="Password too long (max 72 bytes)")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
        # TODO(HTTPS): add secure=True when nginx terminates TLS (roadmap P2).
    )


@router.post("/login", response_model=schemas.MeOut)
def login(data: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == data.username).first()
    # Same 401 for unknown user and wrong password: no username probing.
    if user is None or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    token = auth.create_session(db, user)
    _set_session_cookie(response, token)
    return _me_out(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
    token: str | None = Depends(auth.session_token),
):
    if token:
        auth.revoke_session(db, token)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")


@router.get("/me", response_model=schemas.MeOut)
def me(user: models.User = Depends(auth.get_current_user)):
    return _me_out(user)


@router.put("/me/password", status_code=204)
def change_my_password(
    data: schemas.PasswordChangeIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if not auth.verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    _check_password_bytes(data.new_password)
    user.password_hash = auth.hash_password(data.new_password)
    db.commit()


# ---------- Admin: user management ----------

def _other_active_admin_exists(db: Session, user_id: int) -> bool:
    return (
        db.query(models.User)
        .filter(
            models.User.role == "admin",
            models.User.is_active.is_(True),
            models.User.id != user_id,
        )
        .count()
        > 0
    )


def _get_user_or_404(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_person(db: Session, person_id: int | None) -> None:
    if person_id is not None and db.get(models.Person, person_id) is None:
        raise HTTPException(status_code=422, detail="person_id does not exist")


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    return db.query(models.User).order_by(models.User.username).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    _check_password_bytes(data.password)
    _check_person(db, data.person_id)
    user = models.User(
        username=data.username,
        password_hash=auth.hash_password(data.password),
        role=data.role,
        person_id=data.person_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    user = _get_user_or_404(db, user_id)
    losing_admin = user.role == "admin" and user.is_active and (
        (data.role is not None and data.role != "admin")
        or data.is_active is False
    )
    if losing_admin and not _other_active_admin_exists(db, user.id):
        raise HTTPException(status_code=409, detail="Cannot demote or deactivate the last active admin")
    if data.role is not None:
        user.role = data.role
    if data.clear_person:
        user.person_id = None
    elif data.person_id is not None:
        _check_person(db, data.person_id)
        user.person_id = data.person_id
    if data.is_active is not None:
        user.is_active = data.is_active
        if not user.is_active:
            # A disabled account loses its live sessions immediately.
            db.query(models.AuthSession).filter(models.AuthSession.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/password", status_code=204)
def set_user_password(
    user_id: int,
    data: schemas.UserPasswordSet,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    user = _get_user_or_404(db, user_id)
    _check_password_bytes(data.new_password)
    user.password_hash = auth.hash_password(data.new_password)
    db.commit()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    user = _get_user_or_404(db, user_id)
    if user.role == "admin" and user.is_active and not _other_active_admin_exists(db, user.id):
        raise HTTPException(status_code=409, detail="Cannot delete the last active admin")
    db.query(models.AuthSession).filter(models.AuthSession.user_id == user.id).delete()
    db.delete(user)
    db.commit()
