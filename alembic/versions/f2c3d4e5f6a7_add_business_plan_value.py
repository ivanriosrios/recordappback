"""Add BUSINESS value to plantype enum

Revision ID: f2c3d4e5f6a7
Revises: f1b2c3d4e5f6
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = "f2c3d4e5f6a7"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'business'"))


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un ENUM.
    pass
