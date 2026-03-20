"""rename whatsapp sandbox to pending

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2025-01-02 00:00:00.000000

Si la migración anterior ya se ejecutó con 'sandbox' en el enum,
esta migración lo renombra a 'pending'. Si la anterior ya tenía 'pending',
esto es un no-op seguro.
"""
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Manejo seguro del enum:
    # 1) Si ya existe 'pending', solo migrar filas con valor 'sandbox' a 'pending'.
    # 2) Si no existe 'pending' pero sí 'sandbox', renombrar el valor.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'pending'
                  AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'whatsappstatus')
            ) THEN
                -- pending ya existe: mover filas y listo
                UPDATE businesses SET whatsapp_status = 'pending' WHERE whatsapp_status = 'sandbox';
            ELSIF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'sandbox'
                  AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'whatsappstatus')
            ) THEN
                -- pending no existe, sandbox sí: renombrar el valor
                ALTER TYPE whatsappstatus RENAME VALUE 'sandbox' TO 'pending';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # No revertir: dejar 'pending' como está
    pass
