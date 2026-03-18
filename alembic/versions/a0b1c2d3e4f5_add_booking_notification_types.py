"""Add booking_request and booking_started to notificationtype enum

Revision ID: a0b1c2d3e4f5
Revises: f2a3b4c5d6e7
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = "a0b1c2d3e4f5"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'booking_request'"))
    op.execute(sa.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'booking_started'"))


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un ENUM.
    # Para revertir completamente habría que recrear el tipo con un cast explícito.
    pass
