"""add_notifications_table

Revision ID: c8c9d0d1e2f3
Revises: b7b8b9b0c1d2
Create Date: 2026-03-14 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8c9d0d1e2f3"
down_revision: Union[str, None] = "b7b8b9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear enum para NotificationType
    notificationtype = postgresql.ENUM(
        "reminder_sent",
        "reminder_failed",
        "client_responded",
        "client_optout",
        "follow_up_rated",
        "birthday_sent",
        "reactivation_sent",
        name="notificationtype",
    )
    notificationtype.create(op.get_bind())

    # Crear tabla notifications
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", notificationtype, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_business_id", "notifications", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_business_id", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notificationtype").drop(op.get_bind())
