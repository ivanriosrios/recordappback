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
    # Crear enum con IF NOT EXISTS (compatible con asyncpg)
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
                CREATE TYPE notificationtype AS ENUM (
                    'reminder_sent',
                    'reminder_failed',
                    'client_responded',
                    'client_optout',
                    'follow_up_rated',
                    'birthday_sent',
                    'reactivation_sent'
                );
            END IF;
        END$$;
    """))

    # Crear tabla notifications si no existe
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID NOT NULL PRIMARY KEY,
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            type notificationtype NOT NULL,
            title VARCHAR(200) NOT NULL,
            body TEXT,
            read BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        );
    """))

    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_notifications_business_id
        ON notifications (business_id);
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_business_id;"))
    op.execute(sa.text("DROP TABLE IF EXISTS notifications;"))
    op.execute(sa.text("DROP TYPE IF EXISTS notificationtype;"))
