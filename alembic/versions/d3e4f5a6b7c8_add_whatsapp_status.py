"""add whatsapp_status to businesses

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear el tipo enum en PostgreSQL
    op.execute("CREATE TYPE whatsappstatus AS ENUM ('not_configured', 'sandbox', 'active')")

    # Agregar columna con default 'not_configured'
    op.add_column(
        "businesses",
        sa.Column(
            "whatsapp_status",
            sa.Enum("not_configured", "sandbox", "active", name="whatsappstatus", create_type=False),
            nullable=False,
            server_default="not_configured",
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "whatsapp_status")
    op.execute("DROP TYPE whatsappstatus")
