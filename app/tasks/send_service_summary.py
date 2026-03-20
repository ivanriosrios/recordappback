"""
Task Celery: enviar resumen de servicio al cliente por WhatsApp (KOS-55).

El resumen incluye:
- Nombre del negocio        → {{1}}
- Nombre del servicio       → {{2}}
- Precio cobrado            → {{3}}
- Método de pago            → {{4}}
- Notas del servicio        → {{5}}
- Nombre del cliente        → {{6}}

Si TWILIO_CONTENT_SID_RESUMEN_SERVICIO está configurado en Railway,
usa el template aprobado por WhatsApp (funciona fuera de la ventana 24h).
Si no, cae en texto libre (solo dentro de la ventana de sesión activa).
"""
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.messaging import get_messaging_provider

logger = logging.getLogger(__name__)

PAYMENT_LABELS = {
    "efectivo":      "Efectivo 💵",
    "tarjeta":       "Tarjeta 💳",
    "transferencia": "Transferencia 🏦",
    "otro":          "Otro",
}


@celery_app.task(
    name="app.tasks.send_service_summary.send_service_summary_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def send_service_summary_task(self, service_log_id: str):
    """
    Envía un resumen del servicio al cliente y marca summary_sent=True.

    Flujo:
    1. Carga ServiceLog con cliente, servicio y negocio
    2. Construye mensaje de texto con los datos del cierre
    3. Envía por WhatsApp (proveedor activo)
    4. Marca summary_sent=True en la DB
    """
    from app.models.service_log import ServiceLog
    from app.models.client import Client, ClientStatus
    from app.models.service import Service
    from app.models.business import Business

    session = get_sync_session()
    try:
        log = session.get(ServiceLog, service_log_id)
        if not log:
            logger.warning(f"[service-summary] ServiceLog {service_log_id} no encontrado")
            return

        if log.summary_sent:
            logger.info(f"[service-summary] Log {service_log_id} ya tiene resumen enviado, skip")
            return

        client = session.get(Client, str(log.client_id))
        if not client or client.status == ClientStatus.OPTOUT:
            logger.info(f"[service-summary] Cliente {log.client_id} no disponible o en optout")
            return

        service = session.get(Service, str(log.service_id))
        business = session.get(Business, str(log.business_id))

        service_name = service.name if service else "Servicio"
        business_name = business.name if business else "el negocio"

        price_str = f"${log.price_charged:,.0f}" if log.price_charged is not None else "-"
        method_label = PAYMENT_LABELS.get(log.payment_method, log.payment_method.title()) if log.payment_method else "-"
        notes_str = log.service_notes if log.service_notes else "-"

        provider = get_messaging_provider()

        # Componentes del template — variables {{1}} … {{6}} en orden
        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": business_name},   # {{1}}
                    {"type": "text", "text": service_name},    # {{2}}
                    {"type": "text", "text": price_str},       # {{3}}
                    {"type": "text", "text": method_label},    # {{4}}
                    {"type": "text", "text": notes_str},       # {{5}}
                    {"type": "text", "text": client.display_name},  # {{6}}
                ],
            }
        ]

        # Texto de fallback (usado si no hay content_sid configurado)
        fallback_body = (
            f"✅ *Resumen de servicio — {business_name}*\n\n"
            f"Servicio: {service_name}\n"
            f"Total cobrado: {price_str}\n"
            f"Pago: {method_label}\n"
            f"Notas: {notes_str}\n\n"
            f"Gracias por tu visita, {client.display_name}. ¡Te esperamos pronto! 🙌"
        )

        result = provider.send_template(
            to=client.phone,
            template_name="resumen_servicio",
            language_code="es_CO",
            components=components,
            body_text=fallback_body,
        )

        if result.success:
            log.summary_sent = True
            session.commit()
            logger.info(
                f"[service-summary] Resumen enviado a {client.display_name} "
                f"para log {service_log_id}"
            )
        else:
            logger.error(f"[service-summary] Error enviando a {client.phone}: {result.error}")
            raise self.retry(exc=Exception(result.error))

    except Exception as exc:
        session.rollback()
        logger.exception(f"[service-summary] Error en log {service_log_id}: {exc}")
        raise
    finally:
        session.close()
