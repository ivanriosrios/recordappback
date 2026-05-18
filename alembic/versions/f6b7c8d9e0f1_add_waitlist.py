"""Add waitlist_entries table (idempotente)

Revision ID: f6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.migration_helpers import has_enum, has_table, has_index

revision = "f6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


WL_STATUS = ("pending", "offered", "accepted", "declined", "expired", "removed")


def upgrade() -> None:
    conn = op.get_bind()

    if not has_enum(conn, "waitliststatus"):
        op.execute(sa.text(
            "CREATE TYPE waitliststatus AS ENUM "
            "('pending', 'offered', 'accepted', 'declined', 'expired', 'removed')"
        ))

    if not has_table(conn, "waitlist_entries"):
        op.create_table(
            "waitlist_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("business_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("service_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
            sa.Column("preferred_date", sa.Date(), nullable=True),
            sa.Column("preferred_shift",
                      sa.Enum("morning", "afternoon", "evening",
                              name="appointmentshift", create_type=False),
                      nullable=True),
            sa.Column("status",
                      sa.Enum(*WL_STATUS, name="waitliststatus", create_type=False),
                      nullable=False, server_default="pending"),
            sa.Column("offered_appointment_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("offered_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if not has_index(conn, "ix_waitlist_business_status"):
        op.create_index("ix_waitlist_business_status", "waitlist_entries", ["business_id", "status"])
    if not has_index(conn, "ix_waitlist_client"):
        op.create_index("ix_waitlist_client", "waitlist_entries", ["client_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_waitlist_client")
    op.execute("DROP INDEX IF EXISTS ix_waitlist_business_status")
    op.execute("DROP TABLE IF EXISTS waitlist_entries")
    op.execute("DROP TYPE IF EXISTS waitliststatus")
