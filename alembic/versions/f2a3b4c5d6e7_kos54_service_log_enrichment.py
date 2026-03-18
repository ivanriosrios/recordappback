"""KOS-54: Enriquecer ServiceLog con precio, pago, notas y summary_sent.
         Agregar estimated_duration_minutes a Service.
         Agregar extra_info a Client.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── service_logs: nuevos campos de cierre de servicio ────────────────────
    op.add_column("service_logs",
        sa.Column("price_charged", sa.Numeric(12, 2), nullable=True))
    op.add_column("service_logs",
        sa.Column("payment_method", sa.String(30), nullable=True))
    op.add_column("service_logs",
        sa.Column("service_notes", sa.Text, nullable=True))
    op.add_column("service_logs",
        sa.Column("summary_sent", sa.Boolean, nullable=False,
                  server_default="false"))

    # ── services: duración estimada ──────────────────────────────────────────
    op.add_column("services",
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=True))

    # ── clients: info adicional libre ────────────────────────────────────────
    op.add_column("clients",
        sa.Column("extra_info", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "extra_info")
    op.drop_column("services", "estimated_duration_minutes")
    op.drop_column("service_logs", "summary_sent")
    op.drop_column("service_logs", "service_notes")
    op.drop_column("service_logs", "payment_method")
    op.drop_column("service_logs", "price_charged")
