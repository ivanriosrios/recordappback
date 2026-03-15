"""
Endpoints para historial de servicios y métricas por cliente.

GET /businesses/{business_id}/clients/{client_id}/history
    Retorna: client info, stats, service_logs (últimos 20), reminder_logs (últimos 20)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from uuid import UUID
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client
from app.models.service_log import ServiceLog
from app.models.reminder_log import ReminderLog, LogStatus
from app.models.reminder import Reminder
from app.models.service import Service

router = APIRouter(
    prefix="/businesses/{business_id}/clients",
    tags=["client_history"],
)


@router.get("/{client_id}/history")
async def get_client_history(
    business_id: UUID,
    client_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Obtiene historial completo de un cliente incluyendo:
    - Información del cliente
    - Estadísticas (total servicios, recordatorios, tasa respuesta, etc)
    - Últimos 20 servicios completados
    - Últimos 20 envíos de recordatorios
    """

    # Validar que el cliente pertenece al negocio
    result = await db.execute(
        select(Client).where(
            and_(Client.id == client_id, Client.business_id == business_id)
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )

    # === STATS ===
    # Total servicios
    total_services_result = await db.execute(
        select(func.count(ServiceLog.id)).where(
            and_(
                ServiceLog.client_id == client_id,
                ServiceLog.business_id == business_id,
            )
        )
    )
    total_services = total_services_result.scalar() or 0

    # Total recordatorios enviados
    total_reminders_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            ReminderLog.reminder_id.in_(
                select(Reminder.id).where(Reminder.client_id == client_id)
            )
        )
    )
    total_reminders = total_reminders_result.scalar() or 0

    # Respuestas (SI + NO)
    responses_result = await db.execute(
        select(func.count(ReminderLog.id)).where(
            and_(
                ReminderLog.reminder_id.in_(
                    select(Reminder.id).where(Reminder.client_id == client_id)
                ),
                ReminderLog.status.in_(
                    [LogStatus.RESPONDED_YES, LogStatus.RESPONDED_NO]
                ),
            )
        )
    )
    total_responses = responses_result.scalar() or 0
    response_rate = (
        round((total_responses / total_reminders * 100), 2)
        if total_reminders > 0
        else 0.0
    )

    # Última fecha de servicio
    last_service_result = await db.execute(
        select(ServiceLog.completed_at)
        .where(
            and_(
                ServiceLog.client_id == client_id,
                ServiceLog.business_id == business_id,
            )
        )
        .order_by(desc(ServiceLog.completed_at))
        .limit(1)
    )
    last_service_date = last_service_result.scalar()
    days_since_last_visit = (
        (datetime.utcnow() - last_service_date).days
        if last_service_date
        else None
    )

    # Promedio de rating
    ratings_result = await db.execute(
        select(func.avg(ServiceLog.rating)).where(
            and_(
                ServiceLog.client_id == client_id,
                ServiceLog.rating != None,
            )
        )
    )
    avg_rating = ratings_result.scalar() or 0.0
    avg_rating = round(avg_rating, 1)

    # === SERVICE LOGS (últimos 20) ===
    service_logs_result = await db.execute(
        select(ServiceLog, Service.name).join(
            Service, ServiceLog.service_id == Service.id
        ).where(
            and_(
                ServiceLog.client_id == client_id,
                ServiceLog.business_id == business_id,
            )
        ).order_by(desc(ServiceLog.completed_at)).limit(20)
    )
    service_logs = service_logs_result.all()

    service_logs_list = [
        {
            "id": str(log.ServiceLog.id),
            "service_name": log.name,
            "completed_at": log.ServiceLog.completed_at.isoformat(),
            "rating": log.ServiceLog.rating,
            "notes": log.ServiceLog.notes,
        }
        for log in service_logs
    ]

    # === REMINDER LOGS (últimos 20) ===
    reminder_logs_result = await db.execute(
        select(ReminderLog).join(
            Reminder, ReminderLog.reminder_id == Reminder.id
        ).where(
            Reminder.client_id == client_id
        ).order_by(desc(ReminderLog.sent_at)).limit(20)
    )
    reminder_logs = reminder_logs_result.scalars().all()

    reminder_logs_list = [
        {
            "id": str(log.id),
            "status": log.status,
            "sent_at": log.sent_at.isoformat(),
            "client_response": log.client_response,
            "channel": log.channel,
        }
        for log in reminder_logs
    ]

    return {
        "client": {
            "id": str(client.id),
            "display_name": client.display_name,
            "phone": client.phone,
            "status": client.status,
            "created_at": client.created_at.isoformat(),
        },
        "stats": {
            "total_services": total_services,
            "total_reminders_sent": total_reminders,
            "response_rate": response_rate,
            "avg_rating": avg_rating,
            "last_service_date": (
                last_service_date.isoformat() if last_service_date else None
            ),
            "days_since_last_visit": days_since_last_visit,
        },
        "service_logs": service_logs_list,
        "reminder_logs": reminder_logs_list,
    }
