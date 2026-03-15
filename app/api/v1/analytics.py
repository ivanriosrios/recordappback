from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from uuid import UUID

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client, ClientStatus
from app.models.reminder import Reminder, ReminderStatus
from app.models.reminder_log import ReminderLog, LogStatus
from app.models.service_log import ServiceLog

router = APIRouter(prefix="/businesses/{business_id}/analytics", tags=["analytics"])


@router.get("/")
async def get_business_analytics(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Obtiene métricas de analytics para un negocio.
    Incluye: clientes, recordatorios, logs de envío (últimos 30 días),
    respuestas, post-servicio y service logs.
    """

    # === CLIENTES ===
    # Total clientes
    total_clients_result = await db.execute(
        select(func.count(Client.id)).where(Client.business_id == business_id)
    )
    total_clients = total_clients_result.scalar() or 0

    # Clientes activos
    active_clients_result = await db.execute(
        select(func.count(Client.id)).where(
            and_(
                Client.business_id == business_id,
                Client.status == ClientStatus.ACTIVE,
            )
        )
    )
    active_clients = active_clients_result.scalar() or 0

    # Clientes optout
    optout_clients_result = await db.execute(
        select(func.count(Client.id)).where(
            and_(
                Client.business_id == business_id,
                Client.status == ClientStatus.OPTOUT,
            )
        )
    )
    optout_clients = optout_clients_result.scalar() or 0

    # Clientes at-risk (activos sin actualizar en >60 días)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    at_risk_clients_result = await db.execute(
        select(func.count(Client.id)).where(
            and_(
                Client.business_id == business_id,
                Client.status == ClientStatus.ACTIVE,
                Client.updated_at < sixty_days_ago,
            )
        )
    )
    at_risk_clients = at_risk_clients_result.scalar() or 0

    # === RECORDATORIOS ===
    # Total recordatorios
    total_reminders_result = await db.execute(
        select(func.count(Reminder.id)).where(
            Reminder.client_id.in_(
                select(Client.id).where(Client.business_id == business_id)
            )
        )
    )
    total_reminders = total_reminders_result.scalar() or 0

    # Recordatorios activos
    active_reminders_result = await db.execute(
        select(func.count(Reminder.id)).where(
            and_(
                Reminder.client_id.in_(
                    select(Client.id).where(Client.business_id == business_id)
                ),
                Reminder.status == ReminderStatus.ACTIVE,
            )
        )
    )
    active_reminders = active_reminders_result.scalar() or 0

    # === LOGS DE ENVÍO (últimos 30 días) ===
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Messages sent (SENT, DELIVERED, READ)
    messages_sent_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status.in_(
                    [LogStatus.SENT, LogStatus.DELIVERED, LogStatus.READ]
                ),
            )
        )
    )
    messages_sent = messages_sent_result.scalar() or 0

    # Messages delivered (DELIVERED, READ)
    messages_delivered_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status.in_([LogStatus.DELIVERED, LogStatus.READ]),
            )
        )
    )
    messages_delivered = messages_delivered_result.scalar() or 0

    # Messages read (READ)
    messages_read_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.READ,
            )
        )
    )
    messages_read = messages_read_result.scalar() or 0

    # Messages failed (FAILED)
    messages_failed_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.FAILED,
            )
        )
    )
    messages_failed = messages_failed_result.scalar() or 0

    # === RESPUESTAS (últimos 30 días) ===
    # Responded yes (RESPONDED_YES)
    responded_yes_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.RESPONDED_YES,
            )
        )
    )
    responded_yes = responded_yes_result.scalar() or 0

    # Responded no (RESPONDED_NO)
    responded_no_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.RESPONDED_NO,
            )
        )
    )
    responded_no = responded_no_result.scalar() or 0

    # Response rate
    total_responses = responded_yes + responded_no
    response_rate = (
        (total_responses / messages_sent * 100) if messages_sent > 0 else 0.0
    )

    # === POST-SERVICIO (últimos 30 días) ===
    # Rated good (RATED_GOOD)
    rated_good_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.RATED_GOOD,
            )
        )
    )
    rated_good = rated_good_result.scalar() or 0

    # Rated bad (RATED_BAD)
    rated_bad_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(
                        Reminder.client_id.in_(
                            select(Client.id).where(Client.business_id == business_id)
                        )
                    )
                ),
                ReminderLog.sent_at >= thirty_days_ago,
                ReminderLog.status == LogStatus.RATED_BAD,
            )
        )
    )
    rated_bad = rated_bad_result.scalar() or 0

    # Satisfaction rate
    total_ratings = rated_good + rated_bad
    satisfaction_rate = (rated_good / total_ratings * 100) if total_ratings > 0 else 0.0

    # === SERVICE LOGS (últimos 30 días) ===
    # Services completed
    services_completed_result = await db.execute(
        select(func.count(ServiceLog.id)).where(
            and_(
                ServiceLog.business_id == business_id,
                ServiceLog.completed_at >= thirty_days_ago,
            )
        )
    )
    services_completed = services_completed_result.scalar() or 0

    # Follow-ups sent
    follow_ups_sent_result = await db.execute(
        select(func.count(ServiceLog.id)).where(
            and_(
                ServiceLog.business_id == business_id,
                ServiceLog.completed_at >= thirty_days_ago,
                ServiceLog.follow_up_sent == True,
            )
        )
    )
    follow_ups_sent = follow_ups_sent_result.scalar() or 0

    return {
        # Clientes
        "total_clients": total_clients,
        "active_clients": active_clients,
        "optout_clients": optout_clients,
        "at_risk_clients": at_risk_clients,
        # Recordatorios
        "total_reminders": total_reminders,
        "active_reminders": active_reminders,
        # Logs de envío (últimos 30 días)
        "messages_sent": messages_sent,
        "messages_delivered": messages_delivered,
        "messages_read": messages_read,
        "messages_failed": messages_failed,
        # Respuestas (últimos 30 días)
        "responded_yes": responded_yes,
        "responded_no": responded_no,
        "response_rate": round(response_rate, 2),
        # Post-servicio (últimos 30 días)
        "rated_good": rated_good,
        "rated_bad": rated_bad,
        "satisfaction_rate": round(satisfaction_rate, 2),
        # Service logs (últimos 30 días)
        "services_completed": services_completed,
        "follow_ups_sent": follow_ups_sent,
    }
