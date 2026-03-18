"""Tarea Celery para enviar encuesta de follow-up por WhatsApp."""
import logging
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.send_follow_up")
def send_follow_up_task(service_log_id: str):
    """Envía una encuesta corta al cliente y marca follow_up_sent."""
    from app.models.service_log import ServiceLog
    from app.models.template import Template
    from app.messaging import get_messaging_provider

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

        # Buscar template del sistema para follow-up
        tpl = session.execute(
            select(Template).where(
                Template.business_id == business.id,
                Template.meta_template_name == "encuesta_servicio",
                Template.is_system.is_(True),
            )
        ).scalar_one_or_none()

        meta_name = tpl.meta_template_name if tpl else "encuesta_servicio"
        meta_lang = tpl.meta_language_code if tpl else "es_CO"

        # Enviar encuesta post-servicio usando el proveedor configurado
        provider = get_messaging_provider()
        components = provider.build_body_components(
            client.display_name,
            business.name,
            service.name,
        )
        # Renderizar cuerpo del template si está disponible (para Twilio)
        rendered = None
        if tpl and tpl.body:
            rendered = provider.render_template(
                tpl.body,
                client_name=client.display_name,
                service_name=service.name,
                business_name=business.name,
            )
        provider.send_template(
            to=client.phone,
            template_name=meta_name,
            language_code=meta_lang,
            components=components,
            body_text=rendered,
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
