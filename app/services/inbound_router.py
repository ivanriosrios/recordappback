"""
Orquestador de mensajes entrantes de WhatsApp.

`webhooks.py` debe quedarse como router HTTP fino: parsea Twilio,
valida firma, gestiona idempotency, y delega aquí toda la lógica de
qué hacer con el mensaje.

Pipeline:
    1. Resolver Business por número destino (multi-tenancy).
    2. Resolver Client dentro del scope de ese Business.
    3. Si está en OPTOUT → ignorar.
    4. Si tiene flujo de chatbot activo → ChatbotEngine.
    5. Si hay ReminderLog SENT reciente → handler legacy.
    6. Si hay encuesta pendiente y el intent es rated_* → guardar rating.
    7. Si no hay contexto → ChatbotEngine (keywords / desconocido).
"""
from __future__ import annotations

import logging
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text import strip_whatsapp_prefix, phone_suffix
from app.models.business import Business
from app.models.client import Client, ClientStatus
from app.models.conversation_state import ConversationState, ConversationStep
from app.models.reminder import Reminder
from app.models.reminder_log import ReminderLog, LogStatus
from app.models.service_log import ServiceLog
from app.services.intent_classifier import classify

logger = logging.getLogger(__name__)
settings = get_settings()


def resolve_business(session: Session, to_number: str, *, from_number: str | None = None) -> Business | None:
    """
    Encuentra el Business al que pertenece el número Twilio destino.

    - Modo dedicado (SHARED_WHATSAPP_MODE=False): match exacto por
      sufijo de 10 dígitos de `whatsapp_phone`.
    - Modo compartido (SHARED_WHATSAPP_MODE=True): todos los negocios
      reciben en el mismo número Twilio. Se resuelve el business por
      la conversación más reciente del cliente (último ConversationState,
      último ReminderLog o el negocio del único Client que matchea).
    """
    if not settings.SHARED_WHATSAPP_MODE:
        cleaned = strip_whatsapp_prefix(to_number)
        suffix = phone_suffix(cleaned, 10)
        if not suffix:
            return None
        return (
            session.query(Business)
            .filter(Business.whatsapp_phone.contains(suffix))
            .filter(Business.deleted_at.is_(None))
            .first()
        )

    if not from_number:
        return None

    cleaned_from = strip_whatsapp_prefix(from_number)
    sfx = phone_suffix(cleaned_from, 10)
    if not sfx:
        return None

    matching_clients = (
        session.query(Client)
        .filter(Client.phone.contains(sfx))
        .filter(Client.deleted_at.is_(None))
        .all()
    )
    if not matching_clients:
        return None
    if len(matching_clients) == 1:
        return session.get(Business, matching_clients[0].business_id)

    # Más de un cliente con ese número (mismo número en varios negocios).
    # Prioridad: conversación activa más reciente.
    client_ids = [c.id for c in matching_clients]
    recent_state = (
        session.query(ConversationState)
        .filter(ConversationState.client_id.in_(client_ids))
        .order_by(desc(ConversationState.last_activity))
        .first()
    )
    if recent_state:
        return session.get(Business, recent_state.business_id)

    # Fallback: ReminderLog más reciente que apunta a uno de estos clientes.
    recent_log = (
        session.query(ReminderLog, Reminder.client_id)
        .join(Reminder, ReminderLog.reminder_id == Reminder.id)
        .filter(Reminder.client_id.in_(client_ids))
        .order_by(desc(ReminderLog.sent_at))
        .first()
    )
    if recent_log:
        log, client_id = recent_log
        match = next((c for c in matching_clients if c.id == client_id), None)
        if match:
            return session.get(Business, match.business_id)

    # Último recurso: el primero por orden de creación.
    return session.get(Business, matching_clients[0].business_id)


def find_client(session: Session, business_id, from_number: str) -> Client | None:
    """
    Cliente del negocio, scoped por business_id (NO hace match global).
    """
    cleaned = strip_whatsapp_prefix(from_number)
    suffix = phone_suffix(cleaned, 10)
    if not suffix:
        return None
    return (
        session.query(Client)
        .filter(Client.business_id == business_id)
        .filter(Client.phone.contains(suffix))
        .filter(Client.deleted_at.is_(None))
        .first()
    )


def route_inbound(
    session: Session,
    business: Business,
    client: Client,
    message_text: str,
    wa_message_id: str | None,
) -> None:
    """
    Decide cómo procesar el mensaje. La sesión queda viva en el caller
    (que la commit-eará o cerrará).
    """
    if client.status == ClientStatus.OPTOUT:
        logger.info(f"[inbound] cliente {client.id} en opt-out, ignorando")
        return

    # 1. ¿Flujo de chatbot activo?
    conv = (
        session.query(ConversationState)
        .filter(ConversationState.client_id == client.id)
        .first()
    )
    if conv and conv.step not in (
        ConversationStep.IDLE,
        ConversationStep.COMPLETED,
        ConversationStep.CANCELLED,
    ):
        from app.chatbot import ChatbotEngine
        logger.info(f"[inbound] cliente {client.id} en chatbot ({conv.step})")
        ChatbotEngine(session).handle_message(client.phone, message_text, wa_message_id)
        return

    # 2. ¿Reminder log reciente esperando respuesta?
    last_sent = (
        session.query(ReminderLog)
        .join(Reminder, ReminderLog.reminder_id == Reminder.id)
        .filter(
            and_(Reminder.client_id == client.id, ReminderLog.status == LogStatus.SENT)
        )
        .order_by(desc(ReminderLog.sent_at))
        .first()
    )

    intent = classify(message_text)
    logger.info(f"[inbound] de {client.phone} → '{message_text}' → intent={intent}")

    if last_sent:
        _handle_reminder_reply(session, client, business, last_sent, message_text, intent)
        return

    # 3. ¿Encuesta de follow-up pendiente?
    if intent in ("rated_good", "rated_bad"):
        pending = (
            session.query(ServiceLog)
            .filter(
                ServiceLog.client_id == client.id,
                ServiceLog.follow_up_sent.is_(True),
                ServiceLog.rating.is_(None),
            )
            .order_by(desc(ServiceLog.completed_at))
            .first()
        )
        if pending:
            _save_followup_rating(session, business, client, pending, message_text, intent)
            return

    # 4. ¿Booking intent sin chatbot activo?
    if intent == "booking_intent":
        from app.chatbot import ChatbotEngine
        ChatbotEngine(session).handle_message(client.phone, message_text, wa_message_id)
        return

    # 5. Opt-out vía teclado libre
    if intent == "optout":
        _handle_optout(session, business, client)
        return

    # 6. Sin contexto: dejamos que el chatbot decida (probablemente UNKNOWN).
    from app.chatbot import ChatbotEngine
    ChatbotEngine(session).handle_message(client.phone, message_text, wa_message_id)


# ──────────────────────────────────────────────────────────────────────
# Sub-handlers (mantenidos cortos a propósito)
# ──────────────────────────────────────────────────────────────────────

def _handle_reminder_reply(
    session: Session,
    client: Client,
    business: Business,
    log: ReminderLog,
    message_text: str,
    intent: str,
) -> None:
    from app.services.notifications import create_notification_sync

    intent_to_status = {
        "responded_yes": LogStatus.RESPONDED_YES,
        "responded_no": LogStatus.RESPONDED_NO,
        "rated_good": LogStatus.RATED_GOOD,
        "rated_bad": LogStatus.RATED_BAD,
    }
    new_status = intent_to_status.get(intent)
    if new_status:
        log.status = new_status
        log.client_response = message_text
        session.flush()

    if intent == "responded_yes":
        create_notification_sync(
            session,
            client.business_id,
            "client_responded",
            f"{client.display_name} respondió SI",
            "El cliente confirmó interés en tu servicio.",
        )

    if intent in ("rated_good", "rated_bad"):
        pending = (
            session.query(ServiceLog)
            .filter(
                ServiceLog.client_id == client.id,
                ServiceLog.follow_up_sent.is_(True),
                ServiceLog.rating.is_(None),
            )
            .order_by(desc(ServiceLog.completed_at))
            .first()
        )
        if pending:
            _save_followup_rating(session, business, client, pending, message_text, intent)


def _save_followup_rating(
    session: Session,
    business: Business,
    client: Client,
    log: ServiceLog,
    message_text: str,
    intent: str,
) -> None:
    from app.models.service import Service
    from app.services.notifications import create_notification_sync

    log.rating = 5 if intent == "rated_good" else 1
    rating_text = "bien" if intent == "rated_good" else "mal"
    emoji = "⭐" if intent == "rated_good" else "😟"
    service_name = ""
    if log.service_id:
        svc = session.get(Service, str(log.service_id))
        service_name = f" ({svc.name})" if svc else ""
    create_notification_sync(
        session,
        client.business_id,
        "follow_up_rated",
        f"{emoji} {client.display_name} calificó el servicio: {rating_text}",
        f"Servicio{service_name} — respondió '{message_text}' a la encuesta post-servicio.",
    )
    logger.info(f"[inbound] ServiceLog {log.id} rating → {log.rating}")


def _handle_optout(session: Session, business: Business, client: Client) -> None:
    from app.services.notifications import create_notification_sync

    client.status = ClientStatus.OPTOUT
    create_notification_sync(
        session,
        client.business_id,
        "client_optout",
        f"{client.display_name} se dio de baja",
        f"El cliente {client.display_name} ({client.phone}) ha solicitado no recibir más mensajes.",
    )
    logger.info(f"[inbound] cliente {client.id} → OPTOUT")
