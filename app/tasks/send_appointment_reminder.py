"""
Task Celery: enviar recordatorio de cita 24h antes al cliente.

La tarea es encolada por check_appointment_reminders en scheduler.py.
Marca appointment.reminder_sent = True para no reenviar.
"""
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.messaging import get_messaging_provider

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.send_appointment_reminder.send_appointment_reminder_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def send_appointment_reminder_task(self, appointment_id: str):
    """
    Envía un mensaje WhatsApp al cliente recordándole su cita del día siguiente.

    Flujo:
    1. Carga la cita (debe estar CONFIRMED y reminder_sent=False)
    2. Formatea el mensaje con fecha/hora/servicio/negocio
    3. Envía vía WhatsApp (Twilio o Meta según provider activo)
    4. Marca appointment.reminder_sent = True
    """
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.client import Client, ClientStatus
    from app.models.service import Service
    from app.models.business import Business
    from app.chatbot import messages as MSG
    from app.chatbot.flows.booking import DAY_NAMES, MONTH_NAMES, SHIFT_LABELS

    session = get_sync_session()
    try:
        appt = session.get(Appointment, appointment_id)
        if not appt:
            logger.warning(f"[appt-reminder] Cita {appointment_id} no encontrada")
            return

        if appt.status != AppointmentStatus.CONFIRMED:
            logger.info(f"[appt-reminder] Cita {appointment_id} no está confirmada ({appt.status}), skip")
            return

        if appt.reminder_sent:
            logger.info(f"[appt-reminder] Cita {appointment_id} ya tiene recordatorio enviado, skip")
            return

        client = session.get(Client, str(appt.client_id))
        if not client or client.status == ClientStatus.OPTOUT:
            logger.info(f"[appt-reminder] Cliente {appt.client_id} no disponible o en optout, skip")
            return

        business = session.get(Business, str(appt.business_id))
        business_name = business.name if business else "el negocio"

        service_name = "—"
        if appt.service_id:
            service = session.get(Service, str(appt.service_id))
            if service:
                service_name = service.name

        # Formatear fecha
        day_name = DAY_NAMES[appt.appointment_date.weekday()]
        month = MONTH_NAMES[appt.appointment_date.month]
        date_str = f"{day_name} {appt.appointment_date.day} {month}"

        # Formatear hora/turno
        if appt.appointment_time:
            time_str = str(appt.appointment_time)[:5]
        elif appt.shift:
            from app.models.appointment import AppointmentShift
            time_str = SHIFT_LABELS.get(appt.shift, str(appt.shift))
        else:
            time_str = "—"

        msg = MSG.APPOINTMENT_REMINDER_CLIENT.format(
            name=client.display_name,
            business=business_name,
            service=service_name,
            date=date_str,
            time=time_str,
        )

        provider = get_messaging_provider()
        result = provider.send_text(to=client.phone, body=msg)

        if result.success:
            appt.reminder_sent = True
            session.commit()
            logger.info(
                f"[appt-reminder] Recordatorio enviado a {client.display_name} "
                f"para cita {appointment_id} ({date_str})"
            )
        else:
            logger.error(f"[appt-reminder] Error enviando a {client.phone}: {result.error}")
            raise self.retry(exc=Exception(result.error))

    except Exception as exc:
        session.rollback()
        logger.exception(f"[appt-reminder] Error en cita {appointment_id}: {exc}")
        raise
    finally:
        session.close()
