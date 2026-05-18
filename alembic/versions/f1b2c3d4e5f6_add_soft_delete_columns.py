"""Add deleted_at to businesses and clients (soft-delete)

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = "f1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("clients", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    # Índices parciales para que listados activos sigan siendo rápidos.
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
    op.drop_column("clients", "deleted_at")
    op.drop_column("businesses", "deleted_at")
