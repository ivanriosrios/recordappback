"""Add waitlist_entries table

Revision ID: f6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-05-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


WL_STATUS = ("pending", "offered", "accepted", "declined", "expired", "removed")


def upgrade() -> None:
    wl_status = postgresql.ENUM(*WL_STATUS, name="waitliststatus")
    wl_status.create(op.get_bind(), checkfirst=True)

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
    op.create_index("ix_waitlist_business_status", "waitlist_entries", ["business_id", "status"])
    op.create_index("ix_waitlist_client", "waitlist_entries", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_waitlist_client", table_name="waitlist_entries")
    op.drop_index("ix_waitlist_business_status", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
    op.execute("DROP TYPE IF EXISTS waitliststatus")
