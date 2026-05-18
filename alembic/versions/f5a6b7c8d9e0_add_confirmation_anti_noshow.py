"""Add awaiting_confirmation status + confirmation columns + business toggles

Revision ID: f5a6b7c8d9e0
Revises: f4e5f6a7b8c9
Create Date: 2026-05-18

"""
from alembic import op
import sqlalchemy as sa

revision = "f5a6b7c8d9e0"
down_revision = "f4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TYPE appointmentstatus ADD VALUE IF NOT EXISTS 'awaiting_confirmation'"
    ))
    op.add_column("appointments", sa.Column("confirmation_requested_at", sa.DateTime(), nullable=True))
    op.add_column("appointments", sa.Column("confirmed_by_client_at", sa.DateTime(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("rescued_from_waitlist", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "businesses",
        sa.Column("require_confirmation", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "businesses",
        sa.Column("confirmation_lead_minutes", sa.Integer(), nullable=False, server_default="120"),
    )
    op.add_column(
        "businesses",
        sa.Column("confirmation_window_minutes", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("businesses", "confirmation_window_minutes")
    op.drop_column("businesses", "confirmation_lead_minutes")
    op.drop_column("businesses", "require_confirmation")
    op.drop_column("appointments", "rescued_from_waitlist")
    op.drop_column("appointments", "confirmed_by_client_at")
    op.drop_column("appointments", "confirmation_requested_at")
    # PostgreSQL no permite eliminar valores de un ENUM.
