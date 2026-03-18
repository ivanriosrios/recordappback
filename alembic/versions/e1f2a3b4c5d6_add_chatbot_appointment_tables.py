"""Add chatbot, appointment and business_schedule tables (KOS-49)

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Crear tipos ENUM ─────────────────────────────────────────────────
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'schedulemode') THEN
                CREATE TYPE schedulemode AS ENUM ('time_slots', 'capacity');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointmentstatus') THEN
                CREATE TYPE appointmentstatus AS ENUM (
                    'requested', 'confirmed', 'rejected', 'completed', 'cancelled'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointmentshift') THEN
                CREATE TYPE appointmentshift AS ENUM ('morning', 'afternoon', 'evening');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversationstep') THEN
                CREATE TYPE conversationstep AS ENUM (
                    'idle', 'selecting_service', 'selecting_date',
                    'selecting_slot', 'confirming', 'completed', 'cancelled'
                );
            END IF;
        END$$;
    """))

    # ── 2. Tabla business_schedules ──────────────────────────────────────────
    op.create_table(
        "business_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("mode", sa.Enum("time_slots", "capacity", name="schedulemode",
                                  create_type=False),
                  nullable=False, server_default="time_slots"),
        sa.Column("schedule_data", postgresql.JSONB, nullable=False,
                  server_default="{}"),
        sa.Column("slot_duration_minutes", sa.Integer, nullable=False,
                  server_default="30"),
        sa.Column("max_days_ahead", sa.Integer, nullable=False,
                  server_default="30"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_business_schedules_business_id",
                    "business_schedules", ["business_id"])

    # ── 3. Tabla appointments ────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status",
                  sa.Enum("requested", "confirmed", "rejected", "completed", "cancelled",
                          name="appointmentstatus", create_type=False),
                  nullable=False, server_default="requested"),
        sa.Column("appointment_date", sa.Date, nullable=False),
        sa.Column("appointment_time", sa.String(5), nullable=True),
        sa.Column("shift",
                  sa.Enum("morning", "afternoon", "evening",
                          name="appointmentshift", create_type=False),
                  nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("reminder_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_appointments_business_id", "appointments", ["business_id"])
    op.create_index("ix_appointments_client_id",   "appointments", ["client_id"])
    op.create_index("ix_appointments_date_status", "appointments",
                    ["appointment_date", "status"])

    # ── 4. Tabla conversation_states ─────────────────────────────────────────
    op.create_table(
        "conversation_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clients.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("step",
                  sa.Enum("idle", "selecting_service", "selecting_date",
                          "selecting_slot", "confirming", "completed", "cancelled",
                          name="conversationstep", create_type=False),
                  nullable=False, server_default="idle"),
        sa.Column("context_data", postgresql.JSONB, nullable=False,
                  server_default="{}"),
        sa.Column("last_activity", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_conversation_states_client_id",
                    "conversation_states", ["client_id"])
    op.create_index("ix_conversation_states_last_activity",
                    "conversation_states", ["last_activity"])


def downgrade() -> None:
    op.drop_table("conversation_states")
    op.drop_table("appointments")
    op.drop_table("business_schedules")
    op.execute(sa.text("DROP TYPE IF EXISTS conversationstep;"))
    op.execute(sa.text("DROP TYPE IF EXISTS appointmentshift;"))
    op.execute(sa.text("DROP TYPE IF EXISTS appointmentstatus;"))
    op.execute(sa.text("DROP TYPE IF EXISTS schedulemode;"))
