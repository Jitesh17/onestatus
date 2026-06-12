"""Tiny additive column migration, run at startup after create_all().

create_all() only creates MISSING TABLES; it never adds columns to an existing table.
Until the schema settles enough for Alembic, this helper adds new nullable columns to
already-created databases. Additive and idempotent: existing columns are skipped.
Column detection goes through the SQLAlchemy inspector, so the Postgres profile gets
the same additive columns as SQLite (a PRAGMA-based probe used to skip non-SQLite).
"""
from sqlalchemy import inspect, text


# (table, column, SQL type) — nullable only; anything stricter needs a real migration tool.
# NOTE: whole NEW tables (e.g. `people`, report-scenarios sprint; `users`/`sessions`,
# auth sprint) need no entry here; create_all() creates missing tables fine. This list
# is only for columns added to tables that already exist in deployed DBs.
_COLUMNS = [
    ("updates", "status", "VARCHAR(20)"),
    ("updates", "progress_pct", "INTEGER"),
    ("saved_views", "created_by", "INTEGER"),
]


def run(engine) -> None:
    with engine.connect() as conn:
        for table, column, sqltype in _COLUMNS:
            # Inspector bound to the SAME connection as the ALTER (a separate pooled
            # connection can see a different snapshot), recreated per entry because
            # Inspector caches reflection and two entries may touch the same table.
            inspector = inspect(conn)
            if not inspector.has_table(table):
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}"))
                conn.commit()
