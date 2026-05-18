"""
Webhooks de WhatsApp — únicamente Twilio.

Meta WhatsApp Cloud API queda DEPRECADA tras KOS-38 (migración completada).
El endpoint legacy `/whatsapp` fue eliminado: cualquier integración existente
debe apuntar a `/webhooks/twilio`.

Este módulo es deliberadamente delgado:
  - parsea/valida la firma de Twilio
  - dedup por MessageSid (idempotency)
  - delega TODA la lógica de negocio a `services/inbound_router`

Siempre responde HTTP 200 después del primer ack (Twilio reintenta si no).
"""
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, HTTPException

from app.core.config import get_settings
from app.core.text import strip_whatsapp_prefix, phone_suffix
from app.services.idempotency import already_processed, mark_processed
from app.services.inbound_router import resolve_business, find_client, route_inbound
from app.tasks.db_utils import get_sync_session

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Firma Twilio
# ──────────────────────────────────────────────────────────────────────

def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    """
    Valida la firma X-Twilio-Signature del webhook.

    Política de seguridad:
      - En producción (ENV=production): si no hay TWILIO_WEBHOOK_AUTH_TOKEN
        configurado, se RECHAZA el request (fail-closed).
      - Fuera de producción: si no hay token configurado, se permite (dev mode)
        pero con un warning explícito en logs.
    """
    auth_token = settings.TWILIO_WEBHOOK_AUTH_TOKEN

    if not auth_token:
        if settings.is_production:
            logger.error("[twilio-webhook] TWILIO_WEBHOOK_AUTH_TOKEN ausente en prod — rechazo")
            return False
        logger.warning("[twilio-webhook] sin TWILIO_WEBHOOK_AUTH_TOKEN (dev mode)")
        return True

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)

        params: dict[str, str] = {}
        for key, values in parse_qs(body.decode("utf-8")).items():
            params[key] = values[0] if values else ""

        return validator.validate(url, params, signature)
    except Exception as e:
        logger.error(f"[twilio-webhook] error validando firma: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# Status callback (delivery receipts)
# ──────────────────────────────────────────────────────────────────────

def _update_log_delivery_status(wa_message_id: str, status: str):
    from app.models.reminder_log import ReminderLog, LogStatus

    session = get_sync_session()
    try:
        log = session.query(ReminderLog).filter(
            ReminderLog.wa_message_id == wa_message_id
        ).first()
        if log and log.status == LogStatus.SENT:
            log.status = LogStatus.DELIVERED if status == "delivered" else LogStatus.READ
            session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"[twilio-webhook] error delivery status: {exc}")
    finally:
        session.close()


# ──────────────────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────────────────

@router.post("/twilio")
async def receive_twilio_webhook(request: Request):
    """
    Recibe mensajes entrantes de WhatsApp vía Twilio.

    Campos esperados (application/x-www-form-urlencoded):
      - From: whatsapp:+573001234567
      - To:   whatsapp:+14155238886
      - Body: texto del mensaje
      - MessageSid: ID único
      - SmsStatus / MessageStatus: delivered / read / ...
    """
    try:
        body = await request.body()

        if not _validate_twilio_signature(request, body):
            logger.warning("[twilio-webhook] firma inválida — rechazado")
            raise HTTPException(status_code=403, detail="Firma Twilio inválida")

        form = await request.form()
        from_number = form.get("From", "") or ""
        to_number = form.get("To", "") or ""
        message_body = form.get("Body", "") or ""
        message_sid = form.get("MessageSid", "") or ""
        message_status = (form.get("SmsStatus") or form.get("MessageStatus") or "").strip()

        logger.info(
            f"[twilio-webhook] from={from_number} to={to_number} "
            f"sid={message_sid} status={message_status} body='{message_body[:80]}'"
        )

        # Status callback de delivery — no es mensaje del cliente
        if message_status in ("delivered", "read") and message_sid:
            _update_log_delivery_status(message_sid, message_status)
            return {"status": "ok"}

        # Solo procesamos texto entrante
        if not message_body:
            return {"status": "ok"}

        _dispatch(from_number, to_number, message_body, message_sid)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[twilio-webhook] error inesperado: {exc}")

    # Twilio reintenta si no recibe 200 — siempre OK al final del happy path.
    return {"status": "ok"}


def _dispatch(from_number: str, to_number: str, body: str, sid: str) -> None:
    """
    Toda la lógica vive en una sola sesión SQLAlchemy. Si algo falla,
    rollback completo. Idempotency garantizada por la PK de
    `processed_messages`.
    """
    session = get_sync_session()
    try:
        if sid and already_processed(session, sid):
            logger.info(f"[twilio-webhook] sid={sid} ya procesado — skip")
            return

        business = resolve_business(session, to_number)
        if not business:
            logger.warning(f"[twilio-webhook] To desconocido: {to_number}")
            if sid:
                mark_processed(session, sid)
                session.commit()
            return

        client = find_client(session, business.id, from_number)
        if not client:
            logger.info(
                f"[twilio-webhook] número {from_number} no pertenece a "
                f"business {business.id} — ignorando"
            )
            if sid:
                mark_processed(session, sid)
                session.commit()
            return

        if sid and not mark_processed(session, sid):
            # Otro worker se nos adelantó en la carrera.
            return

        route_inbound(session, business, client, body, sid)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"[twilio-webhook] error en dispatch: {exc}")
    finally:
        session.close()
