"""Task para enviar mensaje de reactivación a clientes inactivos."""
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.services.whatsapp import whatsapp

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.send_reactivation.send_reactivation_task",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def send_reactivation_task(self, client_id: str, business_id: str):
    """
    Envía mensaje de reactivación a un cliente inactivo (sin servicio >60 días).
    """
    session = get_sync_session()
    try:
        from app.models.client import Client, ClientStatus
        from app.models.business import Business
        from app.models.reminder_log import ReminderLog, LogStatus, LogChannel

        client = session.get(Client, client_id)
        business = session.get(Business, business_id)
        if not client or not business:
            logger.warning(
                f"[reactivation] Cliente {client_id} o negocio {business_id} no encontrado"
            )
            return

        if client.status == ClientStatus.OPTOUT:
            logger.info(f"[reactivation] Cliente {client.id} en opt-out, skip")
            return

        # Enviar usando template aprobado por Meta
        components = whatsapp.build_body_components(
            client.display_name,
            business.name,
        )
        result = whatsapp.send_template(
            to=client.phone,
            template_name="reactivacion_cliente",
            language_code="es",
            components=components,
        )

        log = ReminderLog(
            sent_at=datetime.utcnow(),
            channel=LogChannel.WHATSAPP,
            status=LogStatus.SENT if result["success"] else LogStatus.FAILED,
            wa_message_id=result.get("wa_message_id"),
        )
        session.add(log)

        if result["success"]:
            # Marcar cliente como activo de nuevo (no cambiar estado, ya que sigue siendo inactivo)
            # Solo registramos el envío del mensaje
            logger.info(f"[reactivation] Enviado a {client.display_name}")
        else:
            logger.error(f"[reactivation] Fallo: {result.get('error')}")

        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"[reactivation] Error: {exc}")
        raise
    finally:
        session.close()
