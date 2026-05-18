"""Add no_show value to appointmentstatus enum

Revision ID: f4e5f6a7b8c9
Revises: f3d4e5f6a7b8
Create Date: 2026-05-18

"""
from alembic import op
import sqlalchemy as sa

revision = "f4e5f6a7b8c9"
down_revision = "f3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE appointmentstatus ADD VALUE IF NOT EXISTS 'no_show'"))


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un ENUM.
    pass
