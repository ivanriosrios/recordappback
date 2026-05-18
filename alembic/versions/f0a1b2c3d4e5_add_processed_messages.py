"""Add processed_messages table for webhook idempotency (idempotente)

Revision ID: f0a1b2c3d4e5
Revises: e4f5a6b7c8d9
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

from app.core.migration_helpers import has_table, has_index

revision = "f0a1b2c3d4e5"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if not has_table(conn, "processed_messages"):
        op.create_table(
            "processed_messages",
            sa.Column("message_sid", sa.String(length=64), nullable=False),
            sa.Column("provider", sa.String(length=16), nullable=False, server_default="twilio"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("message_sid"),
        )
    if not has_index(conn, "ix_processed_messages_created_at"):
        op.create_index(
            "ix_processed_messages_created_at",
            "processed_messages",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_processed_messages_created_at")
    op.execute("DROP TABLE IF EXISTS processed_messages")
