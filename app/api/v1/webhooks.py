"""
Webhook de WhatsApp Cloud API.

GET  /webhooks/whatsapp — verificación del webhook por Meta
POST /webhooks/whatsapp — recibe eventos (mensajes, status updates)
"""
import logging
from fastapi import APIRouter, Request, Query, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = {"si", "sí", "yes", "ok", "claro", "dale", "listo", "confirmo"}
NEGATIVE_KEYWORDS = {"no", "nop", "cancelar", "cancel"}
GOOD_KEYWORDS     = {"bien", "buen", "excelente", "bueno", "good", "perfecto", "genial"}
BAD_KEYWORDS      = {"mal", "malo", "mala", "bad", "pésimo", "regular", "pesimo"}
OPTOUT_KEYWORDS   = {"salir", "baja", "stop", "unsubscribe", "no quiero", "no mas", "no más"}


def _normalize(text: str) -> str:
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _get_session():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def _classify_response(text: str) -> str:
    t = _normalize(text)
    words = set(t.split())
    if words & OPTOUT_KEYWORDS or any(k in t for k in OPTOUT_KEYWORDS):
        return "optout"
    if words & GOOD_KEYWORDS or any(k in t for k in GOOD_KEYWORDS):
        return "rated_good"
    if words & BAD_KEYWORDS or any(k in t for k in BAD_KEYWORDS):
        return "rated_bad"
    if words & POSITIVE_KEYWORDS:
        return "responded_yes"
    if words & NEGATIVE_KEYWORDS:
        return "responded_no"
    return "unknown"


def _process_message(from_phone: str, message_text: str, wa_message_id: str | None = None):
    from app.models.client import Client, ClientStatus
    from app.models.reminder_log import ReminderLog, LogStatus
    from app.models.reminder import Reminder
    from sqlalchemy import and_, desc

    session = _get_session()
    try:
        intent = _classify_response(message_text)
        logger.info(f"[webhook] De {from_phone} → '{message_text}' → intent={intent}")

        if intent == "unknown":
            return

        # Buscar cliente por teléfono
        phone_suffix = from_phone.replace("+", "").replace(" ", "")[-10:]
        clients = session.query(Client).filter(Client.phone.contains(phone_suffix)).all()
        if not clients:
            logger.warning(f"[webhook] Cliente no encontrado para {from_phone}")
            return
        client = clients[0]

        # Opt-out
        if intent == "optout":
            client.status = ClientStatus.OPTOUT
            session.commit()
            logger.info(f"[webhook] Cliente {client.id} → OPTOUT")
            from app.services.whatsapp import whatsapp
            whatsapp.send_text(
                to=client.phone,
                body=f"Entendido {client.display_name}, no te enviaremos más mensajes."
            )
            return

        # Buscar último log SENT del cliente
        last_log = (
            session.query(ReminderLog)
            .join(Reminder, ReminderLog.reminder_id == Reminder.id)
            .filter(and_(Reminder.client_id == client.id, ReminderLog.status == LogStatus.SENT))
            .order_by(desc(ReminderLog.sent_at))
            .first()
        )
        if not last_log and wa_message_id:
            last_log = session.query(ReminderLog).filter(
                ReminderLog.wa_message_id == wa_message_id
            ).first()

        if not last_log:
            logger.warning(f"[webhook] No se encontró log para cliente {client.id}")
            return

        intent_to_status = {
            "responded_yes": LogStatus.RESPONDED_YES,
            "responded_no":  LogStatus.RESPONDED_NO,
            "rated_good":    LogStatus.RATED_GOOD,
            "rated_bad":     LogStatus.RATED_BAD,
        }
        new_status = intent_to_status.get(intent)
        if new_status:
            last_log.status = new_status
            last_log.client_response = message_text
            session.commit()
            logger.info(f"[webhook] Log {last_log.id} → {new_status}")

        if intent == "responded_yes":
            logger.info(f"[webhook] {client.display_name} confirmó interés → notificar negocio")

        # Actualizar ServiceLog con calificación (bien/mal)
        if intent in ("rated_good", "rated_bad"):
            from app.models.service_log import ServiceLog
            log = (
                session.query(ServiceLog)
                .filter(ServiceLog.client_id == client.id, ServiceLog.follow_up_sent == True)  # noqa: E712
                .order_by(desc(ServiceLog.completed_at))
                .first()
            )
            if log:
                log.rating = 5 if intent == "rated_good" else 1
                session.commit()
                logger.info(f"[webhook] ServiceLog {log.id} rating → {log.rating}")

        if intent == "rated_bad":
            logger.warning(f"[webhook] {client.display_name} calificación MALA → seguimiento")

    except Exception as exc:
        session.rollback()
        logger.exception(f"[webhook] Error: {exc}")
    finally:
        session.close()


def _update_log_delivery_status(wa_message_id: str, status: str):
    from app.models.reminder_log import ReminderLog, LogStatus
    session = _get_session()
    try:
        log = session.query(ReminderLog).filter(
            ReminderLog.wa_message_id == wa_message_id
        ).first()
        if log and log.status == LogStatus.SENT:
            log.status = LogStatus.DELIVERED if status == "delivered" else LogStatus.READ
            session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"[webhook] Error delivery status: {exc}")
    finally:
        session.close()


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """Verificación del webhook por Meta."""
    if hub_mode == "subscribe" and hub_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@router.post("/whatsapp")
async def receive_webhook(request: Request):
    """Recibe eventos de WhatsApp: mensajes de clientes y status updates."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        for msg in value.get("messages", []):
            from_phone = msg.get("from", "")
            wa_msg_id = msg.get("id")
            msg_type = msg.get("type")

            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
                if text:
                    _process_message(from_phone, text, wa_msg_id)
            elif msg_type == "button":
                button_text = msg.get("button", {}).get("text", "")
                if button_text:
                    _process_message(from_phone, button_text, wa_msg_id)

        for status_update in value.get("statuses", []):
            wa_msg_id = status_update.get("id")
            status = status_update.get("status")
            if wa_msg_id and status in ("delivered", "read"):
                _update_log_delivery_status(wa_msg_id, status)

    except Exception as exc:
        logger.exception(f"[webhook] Error procesando evento: {exc}")

    return {"status": "ok"}
