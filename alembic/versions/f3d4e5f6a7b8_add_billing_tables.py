"""Add subscriptions, saas_payments and client_payments (idempotente)

Revision ID: f3d4e5f6a7b8
Revises: f2c3d4e5f6a7
Create Date: 2026-05-18

Esta migración fue rehecha como idempotente: chequea pg_type /
information_schema antes de cada CREATE para que un deploy parcial
previo (que dejó enums o tablas colgadas) no la haga fallar.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.migration_helpers import has_enum, has_table, has_index

revision = "f3d4e5f6a7b8"
down_revision = "f2c3d4e5f6a7"
branch_labels = None
depends_on = None


SUB_STATUS = ("trialing", "active", "past_due", "canceled", "free")
CP_STATUS = ("pending", "approved", "rejected", "refunded", "cancelled")


def upgrade() -> None:
    conn = op.get_bind()

    if not has_enum(conn, "subscriptionstatus"):
        op.execute(sa.text(
            "CREATE TYPE subscriptionstatus AS ENUM "
            "('trialing', 'active', 'past_due', 'canceled', 'free')"
        ))
    if not has_enum(conn, "clientpaymentstatus"):
        op.execute(sa.text(
            "CREATE TYPE clientpaymentstatus AS ENUM "
            "('pending', 'approved', 'rejected', 'refunded', 'cancelled')"
        ))

    if not has_table(conn, "subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("business_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status",
                      sa.Enum(*SUB_STATUS, name="subscriptionstatus", create_type=False),
                      nullable=False, server_default="trialing"),
            sa.Column("plan_name", sa.String(length=50), nullable=False, server_default="Pro"),
            sa.Column("price_usd", sa.Numeric(10, 2), nullable=False, server_default="12.0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("canceled_at", sa.DateTime(), nullable=True),
            sa.Column("granted_free_months", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mp_preapproval_id", sa.String(length=64), nullable=True),
            sa.Column("mp_payer_email", sa.String(length=150), nullable=True),
            sa.Column("mp_init_point", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if not has_index(conn, "uq_subscriptions_business"):
        op.create_index("uq_subscriptions_business", "subscriptions", ["business_id"], unique=True)

    if not has_table(conn, "saas_payments"):
        op.create_table(
            "saas_payments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("mp_payment_id", sa.String(length=64), nullable=True),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if not has_index(conn, "ix_saas_payments_subscription"):
        op.create_index("ix_saas_payments_subscription", "saas_payments", ["subscription_id"])

    if not has_table(conn, "client_payments"):
        op.create_table(
            "client_payments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("business_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
            sa.Column("appointment_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("status",
                      sa.Enum(*CP_STATUS, name="clientpaymentstatus", create_type=False),
                      nullable=False, server_default="pending"),
            sa.Column("mp_preference_id", sa.String(length=64), nullable=True),
            sa.Column("mp_payment_id", sa.String(length=64), nullable=True),
            sa.Column("init_point", sa.String(length=500), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if not has_index(conn, "ix_client_payments_business"):
        op.create_index("ix_client_payments_business", "client_payments", ["business_id"])
    if not has_index(conn, "ix_client_payments_appointment"):
        op.create_index("ix_client_payments_appointment", "client_payments", ["appointment_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_client_payments_appointment")
    op.execute("DROP INDEX IF EXISTS ix_client_payments_business")
    op.execute("DROP TABLE IF EXISTS client_payments")
    op.execute("DROP INDEX IF EXISTS ix_saas_payments_subscription")
    op.execute("DROP TABLE IF EXISTS saas_payments")
    op.execute("DROP INDEX IF EXISTS uq_subscriptions_business")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TYPE IF EXISTS clientpaymentstatus")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
