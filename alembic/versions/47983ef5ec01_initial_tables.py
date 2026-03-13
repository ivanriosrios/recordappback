"""initial_tables

Revision ID: 47983ef5ec01
Revises:
Create Date: 2026-03-12 19:47:10.385333
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '47983ef5ec01'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum types
plan_type = postgresql.ENUM('free', 'basic', 'pro', name='plantype', create_type=False)
channel_type = postgresql.ENUM('whatsapp', 'email', name='channeltype', create_type=False)
client_status = postgresql.ENUM('active', 'inactive', 'optout', name='clientstatus', create_type=False)
template_type = postgresql.ENUM('reminder', 'promo', 'reactivation', name='templatetype', create_type=False)
template_channel = postgresql.ENUM('whatsapp', 'email', name='templatechannel', create_type=False)
reminder_type = postgresql.ENUM('recurring', 'one_time', name='remindertype', create_type=False)
reminder_status = postgresql.ENUM('active', 'paused', 'done', name='reminderstatus', create_type=False)
log_channel = postgresql.ENUM('whatsapp', 'email', 'sms', name='logchannel', create_type=False)
log_status = postgresql.ENUM('sent', 'delivered', 'read', 'responded_yes', 'responded_no', 'failed', name='logstatus', create_type=False)


def upgrade() -> None:
    # Create enum types
    plan_type.create(op.get_bind(), checkfirst=True)
    channel_type.create(op.get_bind(), checkfirst=True)
    client_status.create(op.get_bind(), checkfirst=True)
    template_type.create(op.get_bind(), checkfirst=True)
    template_channel.create(op.get_bind(), checkfirst=True)
    reminder_type.create(op.get_bind(), checkfirst=True)
    reminder_status.create(op.get_bind(), checkfirst=True)
    log_channel.create(op.get_bind(), checkfirst=True)
    log_status.create(op.get_bind(), checkfirst=True)

    # 1. businesses
    op.create_table(
        'businesses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('business_type', sa.String(50), nullable=False, server_default='general'),
        sa.Column('whatsapp_phone', sa.String(15), nullable=False),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('plan', plan_type, nullable=False, server_default='free'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # 2. clients
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('display_name', sa.String(50), nullable=False),
        sa.Column('phone', sa.String(15), nullable=False),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('preferred_channel', channel_type, nullable=False, server_default='whatsapp'),
        sa.Column('status', client_status, nullable=False, server_default='active'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_clients_business_id', 'clients', ['business_id'])

    # 3. services
    op.create_table(
        'services',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ref_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.create_index('ix_services_business_id', 'services', ['business_id'])

    # 4. templates
    op.create_table(
        'templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('type', template_type, nullable=False, server_default='reminder'),
        sa.Column('channel', template_channel, nullable=False, server_default='whatsapp'),
    )
    op.create_index('ix_templates_business_id', 'templates', ['business_id'])

    # 5. reminders
    op.create_table(
        'reminders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', reminder_type, nullable=False, server_default='one_time'),
        sa.Column('recurrence_days', sa.Integer(), nullable=True),
        sa.Column('next_send_date', sa.Date(), nullable=False),
        sa.Column('notify_days_before', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', reminder_status, nullable=False, server_default='active'),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_reminders_client_id', 'reminders', ['client_id'])
    op.create_index('ix_reminders_next_send_date', 'reminders', ['next_send_date'])

    # 6. reminder_logs
    op.create_table(
        'reminder_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reminder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('reminders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('channel', log_channel, nullable=False, server_default='whatsapp'),
        sa.Column('status', log_status, nullable=False, server_default='sent'),
        sa.Column('client_response', sa.Text(), nullable=True),
        sa.Column('wa_message_id', sa.String(100), nullable=True),
    )
    op.create_index('ix_reminder_logs_reminder_id', 'reminder_logs', ['reminder_id'])


def downgrade() -> None:
    op.drop_table('reminder_logs')
    op.drop_table('reminders')
    op.drop_table('templates')
    op.drop_table('services')
    op.drop_table('clients')
    op.drop_table('businesses')

    # Drop enum types
    log_status.drop(op.get_bind(), checkfirst=True)
    log_channel.drop(op.get_bind(), checkfirst=True)
    reminder_status.drop(op.get_bind(), checkfirst=True)
    reminder_type.drop(op.get_bind(), checkfirst=True)
    template_channel.drop(op.get_bind(), checkfirst=True)
    template_type.drop(op.get_bind(), checkfirst=True)
    client_status.drop(op.get_bind(), checkfirst=True)
    channel_type.drop(op.get_bind(), checkfirst=True)
    plan_type.drop(op.get_bind(), checkfirst=True)
