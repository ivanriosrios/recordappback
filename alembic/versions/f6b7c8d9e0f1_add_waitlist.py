"""Add waitlist_entries table (idempotente, SQL crudo)

Revision ID: f6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

from app.core.migration_helpers import has_enum, has_table, has_index

revision = "f6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    if not has_enum(conn, "waitliststatus"):
        op.execute(sa.text(
            "CREATE TYPE waitliststatus AS ENUM "
            "('pending', 'offered', 'accepted', 'declined', 'expired', 'removed')"
        ))

    if not has_table(conn, "waitlist_entries"):
        op.execute(sa.text("""
            CREATE TABLE waitlist_entries (
                id UUID PRIMARY KEY,
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                preferred_date DATE,
                preferred_shift appointmentshift,
                status waitliststatus NOT NULL DEFAULT 'pending',
                offered_appointment_id UUID,
                offered_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

    if not has_index(conn, "ix_waitlist_business_status"):
        op.execute(sa.text(
            "CREATE INDEX ix_waitlist_business_status "
            "ON waitlist_entries (business_id, status)"
        ))
    if not has_index(conn, "ix_waitlist_client"):
        op.execute(sa.text(
            "CREATE INDEX ix_waitlist_client "
            "ON waitlist_entries (client_id)"
        ))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_waitlist_client")
    op.execute("DROP INDEX IF EXISTS ix_waitlist_business_status")
    op.execute("DROP TABLE IF EXISTS waitlist_entries")
    op.execute("DROP TYPE IF EXISTS waitliststatus")
