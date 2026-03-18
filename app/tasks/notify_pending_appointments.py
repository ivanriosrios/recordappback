"""
Task Celery: notificar al negocio sobre citas solicitadas sin confirmar.

Si hay citas en estado REQUESTED con más de N horas sin respuesta,
crea una notificación push para el negocio.
"""
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session

logger = logging.getLogger(__name__)

# Horas sin confirmar antes de enviar alerta al negocio
PENDING_ALERT_HOURS = 4


@celery_app.task(
    name="app.tasks.notify_pending_appointments.notify_pending_appointments_task",
)
def notify_pending_appointments_task():
    """
    Busca citas en estado REQUESTED con más de PENDING_ALERT_HOURS horas
    sin que el negocio las haya confirmado y crea una notificación de alerta.

    Evita notificar duplicado revisando si ya existe una notificación
    tipo 'appointment_pending_alert' reciente para esa cita.
    """
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.client import Client
    from app.models.service import Service
    from app.models.business import Business
    from app.models.notification import Notification
    from app.services.notifications import create_notification_sync
    from app.chatbot.flows.booking import DAY_NAMES, MONTH_NAMES
    from sqlalchemy import and_

    session = get_sync_session()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=PENDING_ALERT_HOURS)

        # Citas solicitadas hace más de PENDING_ALERT_HOURS horas
        pending = (
            session.query(Appointment)
            .filter(
                and_(
                    Appointment.status == AppointmentStatus.REQUESTED,
                    Appointment.created_at <= cutoff,
                )
            )
            .all()
        )

        alerted = 0
        for appt in pending:
            # Verificar si ya enviamos alerta para esta cita recientemente (últimas 8h)
            recent_alert = (
                session.query(Notification)
                .filter(
                    and_(
                        Notification.business_id == appt.business_id,
                        Notification.type == "appointment_pending_alert",
                        Notification.created_at >= datetime.utcnow() - timedelta(hours=8),
                        # Filtramos por referencia a la cita en el body (simple approach)
                        Notification.body.contains(str(appt.id)[:8]),
                    )
                )
                .first()
            )
            if recent_alert:
                continue

            # Obtener info del cliente y servicio para el mensaje
            client = session.get(Client, str(appt.client_id))
            client_name = client.display_name if client else "Cliente"

            service_name = "—"
            if appt.service_id:
                service = session.get(Service, str(appt.service_id))
                if service:
                    service_name = service.name

            day_name = DAY_NAMES[appt.appointment_date.weekday()]
            month = MONTH_NAMES[appt.appointment_date.month]
            date_str = f"{day_name} {appt.appointment_date.day} {month}"

            create_notification_sync(
                session,
                appt.business_id,
                "appointment_pending_alert",
                f"⚠️ Cita pendiente de confirmar: {client_name}",
                f"La cita de {client_name} para *{service_name}* el {date_str} "
                f"(ID: {str(appt.id)[:8]}) lleva más de {PENDING_ALERT_HOURS}h sin confirmación.",
            )
            alerted += 1
            logger.info(
                f"[pending-appts] Alerta enviada para cita {appt.id} "
                f"del negocio {appt.business_id}"
            )

        session.commit()
        logger.info(f"[pending-appts] {alerted} alertas de citas pendientes enviadas")
        return {"alerted": alerted, "checked": len(pending)}

    except Exception as exc:
        session.rollback()
        logger.exception(f"[pending-appts] Error: {exc}")
        raise
    finally:
        session.close()
