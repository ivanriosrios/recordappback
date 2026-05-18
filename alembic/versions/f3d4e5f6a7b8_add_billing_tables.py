"""Add subscriptions, saas_payments and client_payments (idempotente, SQL crudo)

Revision ID: f3d4e5f6a7b8
Revises: f2c3d4e5f6a7
Create Date: 2026-05-18

Usa SQL crudo para CREATE TABLE para evitar el event hook
`_on_table_create` de SQLAlchemy, que en 2.0 intenta crear ENUMs
nativos de PostgreSQL incluso cuando `create_type=False` está seteado
en la columna. Ese hook causaba DuplicateObject en redeploys donde el
ENUM ya existía de un intento previo.
"""
from alembic import op
import sqlalchemy as sa

from app.core.migration_helpers import has_enum, has_table, has_index

revision = "f3d4e5f6a7b8"
down_revision = "f2c3d4e5f6a7"
branch_labels = None
depends_on = None


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
        op.execute(sa.text("""
            CREATE TABLE subscriptions (
                id UUID PRIMARY KEY,
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                status subscriptionstatus NOT NULL DEFAULT 'trialing',
                plan_name VARCHAR(50) NOT NULL DEFAULT 'Pro',
                price_usd NUMERIC(10, 2) NOT NULL DEFAULT 12.0,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                trial_ends_at TIMESTAMP,
                current_period_end TIMESTAMP,
                canceled_at TIMESTAMP,
                granted_free_months INTEGER NOT NULL DEFAULT 0,
                mp_preapproval_id VARCHAR(64),
                mp_payer_email VARCHAR(150),
                mp_init_point VARCHAR(500),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
    if not has_index(conn, "uq_subscriptions_business"):
        op.execute(sa.text(
            "CREATE UNIQUE INDEX uq_subscriptions_business "
            "ON subscriptions (business_id)"
        ))

    if not has_table(conn, "saas_payments"):
        op.execute(sa.text("""
            CREATE TABLE saas_payments (
                id UUID PRIMARY KEY,
                subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
                mp_payment_id VARCHAR(64),
                amount NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                status VARCHAR(32) NOT NULL,
                paid_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
    if not has_index(conn, "ix_saas_payments_subscription"):
        op.execute(sa.text(
            "CREATE INDEX ix_saas_payments_subscription "
            "ON saas_payments (subscription_id)"
        ))

    if not has_table(conn, "client_payments"):
        op.execute(sa.text("""
            CREATE TABLE client_payments (
                id UUID PRIMARY KEY,
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
                appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
                amount NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                status clientpaymentstatus NOT NULL DEFAULT 'pending',
                mp_preference_id VARCHAR(64),
                mp_payment_id VARCHAR(64),
                init_point VARCHAR(500),
                paid_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
    if not has_index(conn, "ix_client_payments_business"):
        op.execute(sa.text(
            "CREATE INDEX ix_client_payments_business "
            "ON client_payments (business_id)"
        ))
    if not has_index(conn, "ix_client_payments_appointment"):
        op.execute(sa.text(
            "CREATE INDEX ix_client_payments_appointment "
            "ON client_payments (appointment_id)"
        ))


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
