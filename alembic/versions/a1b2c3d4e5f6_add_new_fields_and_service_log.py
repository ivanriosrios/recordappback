"""add_new_fields_and_service_log

Revision ID: a1b2c3d4e5f6
Revises: 47983ef5ec01
Create Date: 2026-03-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '47983ef5ec01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Nuevos tipos ENUM ---

    # gendertype
    gendertype = postgresql.ENUM('male', 'female', 'other', name='gendertype')
    gendertype.create(op.get_bind())

    # Agregar valores nuevos al enum templatetype existente
    op.execute("ALTER TYPE templatetype ADD VALUE IF NOT EXISTS 'follow_up'")
    op.execute("ALTER TYPE templatetype ADD VALUE IF NOT EXISTS 'birthday'")

    # Agregar valores nuevos al enum logstatus existente
    op.execute("ALTER TYPE logstatus ADD VALUE IF NOT EXISTS 'rated_good'")
    op.execute("ALTER TYPE logstatus ADD VALUE IF NOT EXISTS 'rated_bad'")

    # --- 2. Nuevas columnas en clients ---
    op.add_column('clients', sa.Column('full_name', sa.String(150), nullable=True))
    op.add_column('clients', sa.Column('birth_date', sa.Date(), nullable=True))
    op.add_column('clients', sa.Column(
        'gender',
        postgresql.ENUM('male', 'female', 'other', name='gendertype', create_type=False),
        nullable=True
    ))

    # --- 3. Nueva columna en services ---
    op.add_column('services', sa.Column('follow_up_days', sa.Integer(), nullable=True))

    # --- 4. Nueva tabla service_logs ---
    op.create_table(
        'service_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('follow_up_sent', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_service_logs_business_id', 'service_logs', ['business_id'])
    op.create_index('ix_service_logs_client_id', 'service_logs', ['client_id'])
    op.create_index('ix_service_logs_service_id', 'service_logs', ['service_id'])
    op.create_index('ix_service_logs_completed_at', 'service_logs', ['completed_at'])


def downgrade() -> None:
    # --- Revertir en orden inverso ---

    # Eliminar tabla service_logs
    op.drop_index('ix_service_logs_completed_at', table_name='service_logs')
    op.drop_index('ix_service_logs_service_id', table_name='service_logs')
    op.drop_index('ix_service_logs_client_id', table_name='service_logs')
    op.drop_index('ix_service_logs_business_id', table_name='service_logs')
    op.drop_table('service_logs')

    # Eliminar columnas de services
    op.drop_column('services', 'follow_up_days')

    # Eliminar columnas de clients
    op.drop_column('clients', 'gender')
    op.drop_column('clients', 'birth_date')
    op.drop_column('clients', 'full_name')

    # Eliminar enum gendertype
    op.execute("DROP TYPE IF EXISTS gendertype")

    # NOTA: PostgreSQL no permite eliminar valores de un ENUM con ALTER TYPE DROP VALUE.
    # Los valores 'follow_up', 'birthday', 'rated_good', 'rated_bad' permanecen en sus enums.
    # Para revertirlos completamente se requiere recrear el enum, lo cual es complejo con datos existentes.
