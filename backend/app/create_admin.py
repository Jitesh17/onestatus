"""First-admin bootstrap and the lockout escape hatch.

Boot path (called from main.py after migrate): if the users table is EMPTY and
ADMIN_PASSWORD is set, create the first admin (ADMIN_USER, default "admin").
An empty table with no env var logs a loud warning naming the fix. A non-empty
table is never touched, so the env vars cannot resurrect a deleted account.

CLI (recover a locked-out server):
    docker compose exec backend python -m app.create_admin [username]
Prompts for a password; creates the user as an active admin, or resets the
password and re-promotes if the username already exists.
"""
import logging
import os
import sys

from sqlalchemy.orm import Session

from . import auth, models

logger = logging.getLogger("onestatus.auth")


def bootstrap_admin(db: Session) -> None:
    if db.query(models.User).count() > 0:
        return
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        logger.warning(
            "No user accounts exist and ADMIN_PASSWORD is not set: nobody can log in. "
            "Set ADMIN_PASSWORD (and optionally ADMIN_USER) and restart, or run "
            "`python -m app.create_admin` inside the backend container."
        )
        return
    username = os.getenv("ADMIN_USER", "admin")
    db.add(models.User(
        username=username,
        password_hash=auth.hash_password(password),
        role="admin",
    ))
    db.commit()
    logger.info("Bootstrapped first admin account %r from ADMIN_PASSWORD", username)


def main() -> int:
    from getpass import getpass
    from .database import SessionLocal

    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = getpass(f"New password for admin {username!r}: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1
    if len(password.encode("utf-8")) > 72:
        print("Password too long (max 72 bytes).", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            db.add(models.User(
                username=username,
                password_hash=auth.hash_password(password),
                role="admin",
            ))
            action = "created"
        else:
            user.password_hash = auth.hash_password(password)
            user.role = "admin"
            user.is_active = True
            action = "reset"
        db.commit()
    print(f"Admin account {username!r} {action}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
