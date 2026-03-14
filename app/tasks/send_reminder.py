"""
Task Celery: enviar un recordatorio por WhatsApp y registrar el log.
"""
import logging
from datetime import datetime, timedelta, date
from celery import shared_task

from app.tasks.celery_app import celery_app
from app.services.whatsapp import whatsapp

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Crea una sesión síncrona para usar dentro de Celery (no async)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings

    settings = get_settings()
    # Convierte asyncpg URL a psycopg2 para uso síncrono en Celery
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(
    name="app.tasks.send_reminder.send_reminder_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutos entre reintentos
)
def send_reminder_task(self, reminder_id: str):
    """
    Envía un recordatorio por WhatsApp y registra el resultado.

    Flujo:
    1. Carga reminder + relaciones
    2. Verifica que siga activo (no fue cancelado mientras esperaba en cola)
    3. Renderiza el mensaje con las variables del cliente/servicio
    4. Llama a WhatsApp Cloud API
    5. Registra ReminderLog (sent / failed)
    6. Si recurrente: actualiza next_send_date
    7. Si one_time: marca status=done
    """
    session = _get_sync_session()

    try:
        from app.models.reminder import Reminder, ReminderStatus, ReminderType
        from app.models.reminder_log import ReminderLog, LogStatus, LogChannel
        from app.models.client import Client
        from app.models.service import Service
        from app.models.template import Template
        from app.models.business import Business

        # Cargar reminder
        reminder = session.get(Reminder, reminder_id)
        if not reminder:
            logger.warning(f"[send_reminder] Reminder {reminder_id} no encontrado")
            return

        if reminder.status != ReminderStatus.ACTIVE:
            logger.info(f"[send_reminder] Reminder {reminder_id} ya no está activo, skip")
            return

        # Cargar relaciones
        client = session.get(Client, str(reminder.client_id))
        service = session.get(Service, str(reminder.service_id))
        template = session.get(Template, str(reminder.template_id))

        # Cargar business para nombre
        business = session.get(Business, str(client.business_id))

        if not all([client, service, template, business]):
            logger.error(f"[send_reminder] Datos incompletos para reminder {reminder_id}")
            return

        # Verificar opt-out
        from app.models.client import ClientStatus
        if client.status == ClientStatus.OPTOUT:
            logger.info(f"[send_reminder] Cliente {client.id} en opt-out, skip")
            reminder.status = ReminderStatus.DONE
            session.commit()
            return

        # Enviar por WhatsApp usando template aprobado por Meta
        # TODO: cuando tengas templates propios aprobados, reemplazar "hello_world"
        #       y pasar components con las variables renderizadas
        result = whatsapp.send_template(
            to=client.phone,
            template_name="hello_world",
            language_code="en_US",
        )

        # Registrar log
        log_status = LogStatus.SENT if result["success"] else LogStatus.FAILED
        log = ReminderLog(
            reminder_id=reminder.id,
            sent_at=datetime.utcnow(),
            channel=LogChannel.WHATSAPP,
            status=log_status,
            wa_message_id=result.get("wa_message_id"),
        )
        session.add(log)

        if result["success"]:
            reminder.last_sent_at = datetime.utcnow()

            if reminder.type == ReminderType.RECURRING and reminder.recurrence_days:
                # Calcular próxima fecha
                reminder.next_send_date = date.today() + timedelta(days=reminder.recurrence_days)
                logger.info(f"[send_reminder] Próximo envío: {reminder.next_send_date}")
            else:
                reminder.status = ReminderStatus.DONE
                logger.info(f"[send_reminder] Reminder {reminder_id} completado")
        else:
            logger.error(f"[send_reminder] Fallo al enviar: {result.get('error')}")
            # Reintento automático
            raise self.retry(exc=Exception(result.get("error", "Error WhatsApp")))

        session.commit()
        logger.info(f"[send_reminder] OK — reminder={reminder_id} status={log_status}")

    except Exception as exc:
        session.rollback()
        logger.exception(f"[send_reminder] Excepción en reminder {reminder_id}: {exc}")
        raise
    finally:
        session.close()
