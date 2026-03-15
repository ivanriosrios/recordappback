"""Tarea Celery para enviar encuesta de follow-up por WhatsApp."""
import logging
from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.send_follow_up")
def send_follow_up_task(service_log_id: str):
    """Envía una encuesta corta al cliente y marca follow_up_sent."""
    from app.models.service_log import ServiceLog
    from app.services.whatsapp import whatsapp

    session = get_sync_session()
    try:
        log = session.get(ServiceLog, service_log_id)
        if not log:
            logger.warning(f"[follow-up] ServiceLog {service_log_id} no encontrado")
            return

        from app.models.client import Client
        from app.models.service import Service
        from app.models.business import Business

        client = session.get(Client, str(log.client_id))
        service = session.get(Service, str(log.service_id))
        if not client or not service:
            logger.warning(f"[follow-up] Datos incompletos en log {service_log_id}")
            return

        business = session.get(Business, str(client.business_id))
        if not business:
            logger.warning(f"[follow-up] Negocio no encontrado para cliente {client.id}")
            return

        # Enviar encuesta post-servicio con template aprobado por Meta
        components = whatsapp.build_body_components(
            client.display_name,
            business.name,
            service.name,
        )
        whatsapp.send_template(
            to=client.phone,
            template_name="encuesta_servicio",
            language_code="es",
            components=components,
        )

        log.follow_up_sent = True
        session.commit()
        logger.info(f"[follow-up] Enviado a cliente {client.id} para servicio {service.id}")
    except Exception as exc:
        session.rollback()
        logger.exception(f"[follow-up] Error: {exc}")
        raise
    finally:
        session.close()
