"""
Task Celery: enviar resumen de servicio al cliente por WhatsApp (KOS-55).

El resumen incluye:
- Nombre del servicio realizado
- Precio cobrado
- Método de pago
- Notas del servicio (si hay)
- Nombre del negocio

Es un texto libre (no un template aprobado por Meta/Twilio) enviado
como mensaje de texto normal. Solo es posible dentro de las 24h de
la última interacción del cliente (ventana de sesión de WhatsApp).
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

        # Construir mensaje
        lines = [
            f"✅ *Resumen de servicio — {business_name}*",
            "",
            f"📋 *Servicio:* {service_name}",
        ]

        if log.price_charged is not None:
            price_str = f"${log.price_charged:,.0f}"
            lines.append(f"💰 *Total cobrado:* {price_str}")

        if log.payment_method:
            method_label = PAYMENT_LABELS.get(log.payment_method, log.payment_method.title())
            lines.append(f"💳 *Pago:* {method_label}")

        if log.service_notes:
            lines.append(f"📝 *Notas:* {log.service_notes}")

        lines.extend([
            "",
            f"Gracias por tu visita, {client.display_name}. ¡Te esperamos pronto! 🙌",
        ])

        message = "\n".join(lines)

        provider = get_messaging_provider()
        result = provider.send_text(to=client.phone, body=message)

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
