"""Task para enviar mensajes de cumpleaños."""
import logging
from datetime import datetime

from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.services.whatsapp import whatsapp

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.send_birthday.send_birthday_task",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def send_birthday_task(self, client_id: str, business_id: str):
    """
    Envía felicitación de cumpleaños por WhatsApp.
    Usa el template del sistema mapeado a Meta.
    """
    session = get_sync_session()
    try:
        from app.models.client import Client, ClientStatus
        from app.models.business import Business
        from app.models.template import Template
        from app.models.reminder_log import ReminderLog, LogStatus, LogChannel

        client = session.get(Client, client_id)
        business = session.get(Business, business_id)
        if not client or not business:
            logger.warning(
                f"[birthday] Cliente {client_id} o negocio {business_id} no encontrado"
            )
            return

        if client.status == ClientStatus.OPTOUT:
            logger.info(f"[birthday] Cliente {client.id} en opt-out, skip")
            return

        # Buscar template del sistema
        tpl = session.execute(
            select(Template).where(
                Template.business_id == business.id,
                Template.meta_template_name == "feliz_cumpleanos",
                Template.is_system.is_(True),
            )
        ).scalar_one_or_none()

        meta_name = tpl.meta_template_name if tpl else "feliz_cumpleanos"
        meta_lang = tpl.meta_language_code if tpl else "es_CO"

        # Enviar usando template aprobado por Meta
        components = whatsapp.build_body_components(
            client.display_name,
            business.name,
        )
        result = whatsapp.send_template(
            to=client.phone,
            template_name=meta_name,
            language_code=meta_lang,
            components=components,
        )

        # Log
        log = ReminderLog(
            sent_at=datetime.utcnow(),
            channel=LogChannel.WHATSAPP,
            status=LogStatus.SENT if result["success"] else LogStatus.FAILED,
            wa_message_id=result.get("wa_message_id"),
        )
        session.add(log)

        if result["success"]:
            logger.info(f"[birthday] Cumpleaños enviado a {client.display_name}")
        else:
            logger.error(f"[birthday] Fallo: {result.get('error')}")

        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"[birthday] Error: {exc}")
        raise
    finally:
        session.close()
