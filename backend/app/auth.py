"""App-managed authentication: password hashing, server-side sessions, role floors.

Design (auth sprint, see the roadmap):
- Local accounts only; auth never leaves the office server. nginx basic auth remains
  an optional outer layer, but the app login is the real gate.
- Sessions are server-side rows keyed by the SHA-256 of an opaque cookie token, so
  logout is a row delete and a copied DB file holds no live sessions.
- CSRF posture: SameSite=Lax cookie and no token machinery. Every state-changing
  endpoint is non-GET, the SPA is same-origin in dev (Vite proxy) and prod (nginx
  proxy), and the audience is an office LAN. Revisit if the app leaves the LAN.
- TODO(HTTPS): set Secure on the cookie when nginx terminates TLS (roadmap P2).
"""
import datetime as dt
import hashlib
import os
import secrets

import bcrypt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .database import get_db

SESSION_COOKIE = "onestatus_session"
SESSION_DAYS = 30


def _rounds() -> int:
    # Tunable so the test suite (BCRYPT_ROUNDS=4) does not pay 12-round cost per login.
    return int(os.getenv("BCRYPT_ROUNDS", "12"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_rounds())).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(db: Session, user: models.User) -> str:
    """Create a session row and return the raw cookie token (stored only as a hash)."""
    token = secrets.token_urlsafe(32)
    db.add(models.AuthSession(
        token_hash=_hash_token(token),
        user_id=user.id,
        expires_at=dt.datetime.utcnow() + dt.timedelta(days=SESSION_DAYS),
    ))
    # Opportunistic cleanup so the table does not grow forever.
    db.query(models.AuthSession).filter(
        models.AuthSession.expires_at < dt.datetime.utcnow()
    ).delete()
    db.commit()
    return token


def revoke_session(db: Session, token: str) -> None:
    db.query(models.AuthSession).filter(
        models.AuthSession.token_hash == _hash_token(token)
    ).delete()
    db.commit()


def resolve_session(db: Session, token: str) -> models.User | None:
    """The user for a live session token, or None (unknown, expired, or inactive)."""
    row = (
        db.query(models.AuthSession)
        .filter(models.AuthSession.token_hash == _hash_token(token))
        .first()
    )
    if row is None or row.expires_at < dt.datetime.utcnow():
        return None
    user = db.get(models.User, row.user_id)
    if user is None or not user.is_active:
        return None
    return user


def session_token(onestatus_session: str | None = Cookie(default=None)) -> str | None:
    """The raw session cookie value, for endpoints that act on the token itself
    (logout revokes the row). The parameter name must match SESSION_COOKIE."""
    return onestatus_session


def get_current_user(
    db: Session = Depends(get_db),
    onestatus_session: str | None = Cookie(default=None),
) -> models.User:
    if not onestatus_session:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = resolve_session(db, onestatus_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user


def _require(floor: str):
    def dep(user: models.User = Depends(get_current_user)) -> models.User:
        if models.ROLE_ORDER.get(user.role, -1) < models.ROLE_ORDER[floor]:
            raise HTTPException(status_code=403, detail=f"Requires {floor} role")
        return user
    return dep


require_member = _require("member")
require_manager = _require("manager")
require_admin = _require("admin")


def author_name(user: models.User) -> str:
    """Display name updates are authored under: the linked person, else the username."""
    return user.person.name if user.person else user.username
