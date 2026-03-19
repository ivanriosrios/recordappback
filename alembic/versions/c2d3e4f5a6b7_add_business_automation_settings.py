"""Add automation settings to businesses table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("inactive_days_threshold", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("businesses", sa.Column("reactivation_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("businesses", sa.Column("birthday_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("businesses", sa.Column("follow_up_auto_enabled", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("businesses", "follow_up_auto_enabled")
    op.drop_column("businesses", "birthday_enabled")
    op.drop_column("businesses", "reactivation_enabled")
    op.drop_column("businesses", "inactive_days_threshold")
