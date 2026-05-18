"""Add deleted_at to businesses and clients (soft-delete) (idempotente)

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

from app.core.migration_helpers import has_column

revision = "f1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if not has_column(conn, "businesses", "deleted_at"):
        op.add_column("businesses", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    if not has_column(conn, "clients", "deleted_at"):
        op.add_column("clients", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_businesses_active "
        "ON businesses (id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clients_business_active "
        "ON clients (business_id) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_clients_business_active")
    op.execute("DROP INDEX IF EXISTS ix_businesses_active")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS deleted_at")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS deleted_at")
