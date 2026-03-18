"""
Webhook de WhatsApp Cloud API.

GET  /webhooks/whatsapp — verificación del webhook por Meta
POST /webhooks/whatsapp — recibe eventos (mensajes, status updates)
"""
import logging
from fastapi import APIRouter, Request, Query, HTTPException
from app.core.config import get_settings
from app.tasks.db_utils import get_sync_session

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = {"si", "sí", "yes", "ok", "claro", "dale", "listo", "confirmo"}
NEGATIVE_KEYWORDS = {"no", "nop", "cancelar", "cancel"}
GOOD_KEYWORDS     = {"bien", "buen", "excelente", "bueno", "good", "perfecto", "genial", "1", "2"}
BAD_KEYWORDS      = {"mal", "malo", "mala", "bad", "pésimo", "regular", "pesimo", "3", "4"}
OPTOUT_KEYWORDS   = {"salir", "baja", "stop", "unsubscribe", "no quiero", "no mas", "no más"}
BOOKING_KEYWORDS  = {"cita", "agendar", "reservar", "turno", "quiero cita", "quiero turno", "hora",
                     "appointment", "book", "reserva", "cuando", "disponible", "agenda"}


def _normalize(text: str) -> str:
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _get_session():
    return get_sync_session()


def _classify_response(text: str) -> str:
    t = _normalize(text)
    words = set(t.split())
    if words & OPTOUT_KEYWORDS or any(k in t for k in OPTOUT_KEYWORDS):
        return "optout"
    if any(k in t for k in BOOKING_KEYWORDS):
        return "booking_intent"
    if words & GOOD_KEYWORDS or any(k in t for k in GOOD_KEYWORDS):
        return "rated_good"
    if words & BAD_KEYWORDS or any(k in t for k in BAD_KEYWORDS):
        return "rated_bad"
    if words & POSITIVE_KEYWORDS:
        return "responded_yes"
    if words & NEGATIVE_KEYWORDS:
        return "responded_no"
    return "unknown"


def _handle_booking_intent(session, client, message_text: str):
    """
    KOS-60: Router de contexto para mensajes de agendamiento.
    Si el negocio tiene chatbot activo (BusinessSchedule), inicia el flujo.
    De lo contrario, notifica al admin que hay un cliente interesado.
    """
    from app.models.business_schedule import BusinessSchedule
    from app.models.conversation_state import ConversationState, ConversationStep
    from app.services.notifications import create_notification_sync

    try:
        # Verificar si el negocio tiene horario configurado
        sched = session.query(BusinessSchedule).filter(
            BusinessSchedule.business_id == client.business_id,
            BusinessSchedule.is_active.is_(True),
        ).first()

        if not sched:
            # Sin chatbot activo → crear notificación para el admin
            create_notification_sync(
                session,
                client.business_id,
                "booking_request",
                f"{client.display_name} quiere agendar una cita",
                f"El cliente {client.display_name} ({client.phone}) preguntó por disponibilidad. Contáctalo para agendar.",
            )
            logger.info(f"[webhook] booking_intent sin chatbot → notificación creada para {client.business_id}")
            return

        # Verificar/crear ConversationState
        state = session.query(ConversationState).filter(
            ConversationState.client_id == client.id
        ).first()

        if not state:
            state = ConversationState(
                business_id=client.business_id,
                client_id=client.id,
                step=ConversationStep.IDLE,
                context_data={},
            )
            session.add(state)
            session.flush()

        # Si ya está en un flujo activo, no reiniciar
        if state.step != ConversationStep.IDLE:
            logger.info(f"[webhook] Cliente {client.id} ya tiene flujo activo en step={state.step}")
            return

        # Iniciar flujo de agendamiento — crear notificación para que el admin gestione
        state.step = ConversationStep.SELECTING_SERVICE
        state.context_data = {"message": message_text}
        from datetime import datetime
        state.last_activity = datetime.utcnow()

        create_notification_sync(
            session,
            client.business_id,
            "booking_started",
            f"{client.display_name} quiere agendar una cita",
            f"El cliente {client.display_name} ({client.phone}) inició el flujo de agendamiento.",
        )
        session.commit()
        logger.info(f"[webhook] booking_intent → flujo iniciado para cliente {client.id}")

        # Enviar respuesta inicial al cliente
        try:
            from app.services.whatsapp import whatsapp
            from app.models.service import Service
            services = session.query(Service).filter(
                Service.business_id == client.business_id,
                Service.is_active.is_(True),
            ).limit(10).all()

            if services:
                service_list = "\n".join(
                    f"  {i+1}. {s.name}" + (f" (${float(s.ref_price):,.0f})" if s.ref_price else "")
                    for i, s in enumerate(services)
                )
                msg = (
                    f"¡Hola {client.display_name}! 👋\n\n"
                    f"Estos son nuestros servicios disponibles:\n{service_list}\n\n"
                    f"Responde con el *número* del servicio que deseas o escribe directamente el nombre."
                )
                whatsapp.send_text(to=client.phone, body=msg)
        except Exception as exc:
            logger.warning(f"[webhook] No se pudo enviar menú de servicios: {exc}")

    except Exception as exc:
        session.rollback()
        logger.exception(f"[webhook] Error en booking_intent: {exc}")


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

        # KOS-60: Si hay una conversación activa, redirigir al handler del chatbot
        if intent not in ("optout",):
            from app.models.conversation_state import ConversationState, ConversationStep
            conv = (
                session.query(ConversationState)
                .filter(ConversationState.client_id == client.id)
                .first()
            )
            if conv and conv.step not in (ConversationStep.IDLE, ConversationStep.COMPLETED, ConversationStep.CANCELLED):
                # Hay un flujo de chatbot activo — no procesar como respuesta a reminder
                logger.info(f"[webhook] Cliente {client.id} en chatbot step={conv.step}, ignorando como reminder")
                return

        # Booking intent (KOS-60)
        if intent == "booking_intent":
            _handle_booking_intent(session, client, message_text)
            return

        # Opt-out
        if intent == "optout":
            from app.services.notifications import create_notification_sync

            client.status = ClientStatus.OPTOUT
            # Crear notificación antes de commit
            create_notification_sync(
                session,
                client.business_id,
                "client_optout",
                f"{client.display_name} se dio de baja",
                f"El cliente {client.display_name} ({client.phone}) ha solicitado no recibir más mensajes.",
            )
            session.commit()
            logger.info(f"[webhook] Cliente {client.id} → OPTOUT")
            from app.services.whatsapp import whatsapp
            from app.models.business import Business
            from app.models.template import Template
            from sqlalchemy import select as sa_select

            business = session.get(Business, str(client.business_id))
            business_name = business.name if business else "nuestro negocio"

            # Buscar template del sistema para opt-out
            tpl = session.execute(
                sa_select(Template).where(
                    Template.business_id == client.business_id,
                    Template.meta_template_name == "confirmacion_optout",
                    Template.is_system.is_(True),
                )
            ).scalar_one_or_none()

            meta_name = tpl.meta_template_name if tpl else "confirmacion_optout"
            meta_lang = tpl.meta_language_code if tpl else "es_CO"

            components = whatsapp.build_body_components(
                client.display_name,
                business_name,
            )
            whatsapp.send_template(
                to=client.phone,
                template_name=meta_name,
                language_code=meta_lang,
                components=components,
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
            from app.services.notifications import create_notification_sync

            create_notification_sync(
                session,
                client.business_id,
                "client_responded",
                f"{client.display_name} respondió SI",
                f"El cliente confirmó interés en tu servicio.",
            )
            logger.info(
                f"[webhook] {client.display_name} confirmó interés → notificar negocio"
            )

        # Actualizar ServiceLog con calificación (bien/mal)
        if intent in ("rated_good", "rated_bad"):
            from app.models.service_log import ServiceLog
            from app.services.notifications import create_notification_sync

            log = (
                session.query(ServiceLog)
                .filter(ServiceLog.client_id == client.id, ServiceLog.follow_up_sent == True)  # noqa: E712
                .order_by(desc(ServiceLog.completed_at))
                .first()
            )
            if log:
                log.rating = 5 if intent == "rated_good" else 1
                rating_text = "bien" if intent == "rated_good" else "mal"
                create_notification_sync(
                    session,
                    client.business_id,
                    "follow_up_rated",
                    f"{client.display_name} calificó el servicio: {rating_text}",
                    f"El cliente ha respondido la encuesta post-servicio.",
                )
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
