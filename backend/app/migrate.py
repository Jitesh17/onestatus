"""Tiny additive column migration, run at startup after create_all().

create_all() only creates MISSING TABLES; it never adds columns to an existing table.
Until the schema settles enough for Alembic, this helper adds new nullable columns to
already-created SQLite databases. Additive and idempotent: existing columns are skipped.
"""
from sqlalchemy import text


# (table, column, SQL type) — nullable only; anything stricter needs a real migration tool.
_COLUMNS = [
    ("updates", "status", "VARCHAR(20)"),
    ("updates", "progress_pct", "INTEGER"),
]


def run(engine) -> None:
    with engine.connect() as conn:
        for table, column, sqltype in _COLUMNS:
            try:
                existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            except Exception:
                # Non-SQLite backend (no PRAGMA): rely on create_all / future Alembic instead.
                return
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}"))
                conn.commit()
