"""Tarea Celery para enviar encuesta de follow-up por WhatsApp."""
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


@celery_app.task(name="app.tasks.send_follow_up")
def send_follow_up_task(service_log_id: str):
    """Envía una encuesta corta al cliente y marca follow_up_sent."""
    from app.models.service_log import ServiceLog
    from app.services.whatsapp import whatsapp

    session = _get_session()
    try:
        log = session.get(ServiceLog, service_log_id)
        if not log:
            logger.warning(f"[follow-up] ServiceLog {service_log_id} no encontrado")
            return

        client = log.client
        service = log.service
        if not client or not service:
            logger.warning(f"[follow-up] Datos incompletos en log {service_log_id}")
            return

        body = (
            f"Hola {client.display_name}, ¿cómo te fue con el servicio '{service.name}'? "
            "Responde 'bien' o 'mal'."
        )
        whatsapp.send_text(to=client.phone, body=body)

        log.follow_up_sent = True
        session.commit()
        logger.info(f"[follow-up] Enviado a cliente {client.id} para servicio {service.id}")
    except Exception as exc:
        session.rollback()
        logger.exception(f"[follow-up] Error: {exc}")
        raise
    finally:
        session.close()
