"""Add meta template fields and seed system templates

Revision ID: d9e0f1a2b3c4
Revises: c8c9d0d1e2f3
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b3c4"
down_revision = "c8c9d0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Crear enum templatestatus si no existe
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'templatestatus') THEN
                CREATE TYPE templatestatus AS ENUM ('approved', 'pending', 'rejected');
            END IF;
        END$$;
    """))

    # 2. Agregar columnas nuevas
    op.execute(sa.text("""
        ALTER TABLE templates
            ADD COLUMN IF NOT EXISTS meta_template_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS meta_language_code VARCHAR(10) NOT NULL DEFAULT 'es',
            ADD COLUMN IF NOT EXISTS status templatestatus NOT NULL DEFAULT 'approved',
            ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        ALTER TABLE templates
            DROP COLUMN IF EXISTS meta_template_name,
            DROP COLUMN IF EXISTS meta_language_code,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS is_system;
    """))
    op.execute(sa.text("DROP TYPE IF EXISTS templatestatus;"))
