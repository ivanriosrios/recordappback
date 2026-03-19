"""Add appointment_requested to notificationtype enum

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'appointment_requested'"))


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un ENUM.
    pass
