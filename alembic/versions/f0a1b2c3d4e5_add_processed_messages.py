"""Add processed_messages table for webhook idempotency

Revision ID: f0a1b2c3d4e5
Revises: e4f5a6b7c8d9
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e5"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_messages",
        sa.Column("message_sid", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False, server_default="twilio"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("message_sid"),
    )
    op.create_index(
        "ix_processed_messages_created_at",
        "processed_messages",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_processed_messages_created_at", table_name="processed_messages")
    op.drop_table("processed_messages")
