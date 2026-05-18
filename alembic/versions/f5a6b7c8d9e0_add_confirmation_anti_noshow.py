"""Add awaiting_confirmation + confirmation columns (idempotente)

Revision ID: f5a6b7c8d9e0
Revises: f4e5f6a7b8c9
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

from app.core.migration_helpers import has_column

revision = "f5a6b7c8d9e0"
down_revision = "f4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ALTER TYPE ... ADD VALUE IF NOT EXISTS ya es idempotente.
    op.execute(sa.text(
        "ALTER TYPE appointmentstatus ADD VALUE IF NOT EXISTS 'awaiting_confirmation'"
    ))

    if not has_column(conn, "appointments", "confirmation_requested_at"):
        op.add_column("appointments", sa.Column("confirmation_requested_at", sa.DateTime(), nullable=True))
    if not has_column(conn, "appointments", "confirmed_by_client_at"):
        op.add_column("appointments", sa.Column("confirmed_by_client_at", sa.DateTime(), nullable=True))
    if not has_column(conn, "appointments", "rescued_from_waitlist"):
        op.add_column(
            "appointments",
            sa.Column("rescued_from_waitlist", sa.Boolean(), nullable=False, server_default="false"),
        )

    if not has_column(conn, "businesses", "require_confirmation"):
        op.add_column(
            "businesses",
            sa.Column("require_confirmation", sa.Boolean(), nullable=False, server_default="true"),
        )
    if not has_column(conn, "businesses", "confirmation_lead_minutes"):
        op.add_column(
            "businesses",
            sa.Column("confirmation_lead_minutes", sa.Integer(), nullable=False, server_default="120"),
        )
    if not has_column(conn, "businesses", "confirmation_window_minutes"):
        op.add_column(
            "businesses",
            sa.Column("confirmation_window_minutes", sa.Integer(), nullable=False, server_default="30"),
        )


def downgrade() -> None:
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS confirmation_window_minutes")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS confirmation_lead_minutes")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS require_confirmation")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS rescued_from_waitlist")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmed_by_client_at")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_requested_at")
    # PostgreSQL no permite eliminar valores de un ENUM.
