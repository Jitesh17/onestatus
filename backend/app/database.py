"""Database engine and session setup.

Defaults to a local SQLite file so the app runs with zero setup in week 1.
Set DATABASE_URL (e.g. the Postgres URL from docker-compose) to switch.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./onestatus.db")

# check_same_thread is a SQLite-only flag; harmless to compute conditionally.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
