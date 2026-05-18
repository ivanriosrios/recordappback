"""
Helpers de idempotencia para migraciones en producción.

PostgreSQL no soporta `CREATE TYPE IF NOT EXISTS` directamente, y
`op.create_table`/`op.add_column` tampoco son idempotentes. Si una
migración falla a mitad (deja un enum colgado, p. ej.), el siguiente
deploy entra en bucle de error. Estos helpers chequean el catálogo
antes de cada operación.
"""
from __future__ import annotations

import sqlalchemy as sa


def has_enum(conn, name: str) -> bool:
    return conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :n"),
        {"n": name},
    ).scalar() is not None


def has_table(conn, name: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :n"
        ),
        {"n": name},
    ).scalar() is not None


def has_column(conn, table: str, column: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar() is not None


def has_index(conn, name: str) -> bool:
    return conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": name},
    ).scalar() is not None
