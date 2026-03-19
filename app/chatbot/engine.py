"""
ChatbotEngine — router principal de mensajes entrantes de WhatsApp.

Recibe un teléfono + texto y decide qué hacer:
1. Si el cliente no existe → ignorar (no es cliente del negocio)
2. Si el cliente tiene una conversación activa → continuar el flujo
3. Si el cliente envió una keyword de activación → iniciar flujo de agendamiento
4. Si es respuesta a un recordatorio → delegar al webhook legacy de reminder_log

Este módulo NO importa de api/ ni de tasks/. Es puro dominio.
"""
import logging
import unicodedata
from datetime import datetime, date

from sqlalchemy.orm import Session

from app.models.client import Client, ClientStatus
from app.models.business import Business
from app.models.service import Service
from app.models.appointment import Appointment, AppointmentStatus
from app.models.conversation_state import ConversationState, ConversationStep
from app.models.business_schedule import BusinessSchedule
from app.chatbot import messages as MSG
from app.chatbot.flows.booking import (
    handle_selecting_service,
    handle_selecting_date,
    handle_selecting_slot,
    build_confirmation_message,
    build_service_selection_message,
    build_date_selection_message,
    build_slot_selection_message,
    _format_time_display,
    DAY_NAMES, MONTH_NAMES,
)
from app.messaging import get_messaging_provider

logger = logging.getLogger(__name__)

# Keywords que activan el flujo de agendamiento
BOOKING_KEYWORDS = {
    "cita", "agendar", "reservar", "turno", "quiero cita",
    "necesito cita", "appointment", "quiero agendar", "si", "sí", "yes",
}

# Keywords de cancelación durante un flujo activo
CANCEL_KEYWORDS = {"no", "cancelar", "cancel", "salir", "exit"}

# Tiempo de expiración de conversación sin actividad (horas)
CONVERSATION_TIMEOUT_HOURS = 2


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


class ChatbotEngine:
    """
    Motor principal del chatbot de agendamiento.
    Una instancia por request (recibe la sesión síncrona de Celery/webhook).
    """

    def __init__(self, session: Session):
        self.session = session
        self.provider = get_messaging_provider()

    def handle_message(self, phone: str, text: str, wa_message_id: str | None = None) -> None:
        """
        Punto de entrada principal. Procesa un mensaje entrante de WhatsApp.

        Args:
            phone: número del cliente (solo dígitos, sin +)
            text: texto del mensaje
            wa_message_id: ID del mensaje de Twilio/Meta (opcional)
        """
        try:
            # 1. Buscar cliente por teléfono
            client = self._find_client(phone)
            if not client:
                logger.info(f"[chatbot] Mensaje de número desconocido {phone}, ignorando")
                return

            # 2. Verificar opt-out
            if client.status == ClientStatus.OPTOUT:
                logger.info(f"[chatbot] Cliente {client.id} en opt-out, ignorando")
                return

            # 3. Cargar o inicializar estado de conversación
            state = self._get_or_create_state(client)

            # 4. Verificar si la conversación expiró
            if self._is_expired(state):
                logger.info(f"[chatbot] Conversación expirada para cliente {client.id}, reseteando")
                self._reset_state(state)

            # 5. Procesar según el paso actual
            self._route_message(client, state, text)

        except Exception as exc:
            logger.exception(f"[chatbot] Error procesando mensaje de {phone}: {exc}")
            self.session.rollback()

    def _find_client(self, phone: str) -> Client | None:
        """Busca cliente por sufijo de teléfono (últimos 10 dígitos)."""
        suffix = phone.replace("+", "").replace(" ", "")[-10:]
        clients = (
            self.session.query(Client)
            .filter(Client.phone.contains(suffix))
            .all()
        )
        return clients[0] if clients else None

    def _get_or_create_state(self, client: Client) -> ConversationState:
        """Retorna el estado de conversación del cliente, o crea uno nuevo."""
        state = (
            self.session.query(ConversationState)
            .filter(ConversationState.client_id == client.id)
            .first()
        )
        if not state:
            state = ConversationState(
                business_id=client.business_id,
                client_id=client.id,
                step=ConversationStep.IDLE,
                context_data={},
                last_activity=datetime.utcnow(),
            )
            self.session.add(state)
            self.session.flush()
        return state

    def _is_expired(self, state: ConversationState) -> bool:
        """Verifica si la conversación expiró por inactividad."""
        if state.step == ConversationStep.IDLE:
            return False
        delta = datetime.utcnow() - state.last_activity
        return delta.total_seconds() > CONVERSATION_TIMEOUT_HOURS * 3600

    def _reset_state(self, state: ConversationState) -> None:
        state.step = ConversationStep.IDLE
        state.context_data = {}
        state.last_activity = datetime.utcnow()
        self.session.flush()

    def _send(self, phone: str, text: str) -> None:
        """Envía un mensaje al cliente."""
        try:
            result = self.provider.send_text(to=phone, body=text)
            if not result.success:
                logger.error(f"[chatbot] Error enviando a {phone}: {result.error}")
        except Exception as e:
            logger.error(f"[chatbot] Excepción enviando a {phone}: {e}")

    def _get_business(self, business_id) -> Business | None:
        return self.session.get(Business, str(business_id))

    def _get_schedule(self, business_id) -> BusinessSchedule | None:
        return (
            self.session.query(BusinessSchedule)
            .filter(
                BusinessSchedule.business_id == business_id,
                BusinessSchedule.is_active.is_(True),
            )
            .first()
        )

    def _get_active_services(self, business_id) -> list[Service]:
        return (
            self.session.query(Service)
            .filter(
                Service.business_id == business_id,
                Service.is_active.is_(True),
            )
            .order_by(Service.name)
            .all()
        )

    def _route_message(self, client: Client, state: ConversationState, text: str) -> None:
        """Enruta el mensaje según el paso actual de la conversación."""
        t = _normalize(text)
        business = self._get_business(client.business_id)
        if not business:
            return

        # ── IDLE: sin conversación activa ────────────────────────────────────
        if state.step == ConversationStep.IDLE:
            if any(kw in t for kw in BOOKING_KEYWORDS) or t in BOOKING_KEYWORDS:
                self._start_booking(client, state, business)
            else:
                # No es una keyword de agendamiento → mensaje genérico
                self._send(client.phone, MSG.UNKNOWN_RESPONSE)
            return

        # ── Cancelación en cualquier paso activo ─────────────────────────────
        if t in CANCEL_KEYWORDS and state.step not in (
            ConversationStep.COMPLETED, ConversationStep.CANCELLED
        ):
            self._reset_state(state)
            self.session.commit()
            self._send(client.phone, MSG.BOOKING_CANCELLED)
            return

        # ── SELECTING_SERVICE ────────────────────────────────────────────────
        if state.step == ConversationStep.SELECTING_SERVICE:
            services = self._get_active_services(client.business_id)
            error_msg = handle_selecting_service(text, state, services)
            if error_msg:
                self.session.commit()
                self._send(client.phone, error_msg)
                return

            # Servicio elegido → pedir fecha
            schedule = self._get_schedule(client.business_id)
            if not schedule:
                self._reset_state(state)
                self.session.commit()
                self._send(client.phone,
                    "Lo siento, el agendamiento no está disponible en este momento. "
                    "Contáctanos directamente. 🙏")
                return

            self.session.commit()
            service_name = state.context_data.get("service_name", "")
            self._send(client.phone,
                build_date_selection_message(service_name, schedule))
            return

        # ── SELECTING_DATE ───────────────────────────────────────────────────
        if state.step == ConversationStep.SELECTING_DATE:
            schedule = self._get_schedule(client.business_id)
            if not schedule:
                self._reset_state(state)
                self.session.commit()
                self._send(client.phone, "Agendamiento no disponible. Contáctanos. 🙏")
                return

            error_msg, chosen_date = handle_selecting_date(text, state, schedule)
            if error_msg:
                self.session.commit()
                self._send(client.phone, error_msg)
                return

            # Guardar fecha y avanzar
            state.context_data = {
                **state.context_data,
                "appointment_date": chosen_date.isoformat(),
            }
            state.step = ConversationStep.SELECTING_SLOT
            state.last_activity = datetime.utcnow()
            self.session.commit()
            self._send(client.phone,
                build_slot_selection_message(chosen_date, schedule))
            return

        # ── SELECTING_SLOT ───────────────────────────────────────────────────
        if state.step == ConversationStep.SELECTING_SLOT:
            schedule = self._get_schedule(client.business_id)
            chosen_date = date.fromisoformat(state.context_data["appointment_date"])
            error_msg = handle_selecting_slot(text, state, schedule, chosen_date)
            if error_msg:
                self.session.commit()
                self._send(client.phone, error_msg)
                return

            self.session.commit()
            self._send(client.phone, build_confirmation_message(state))
            return

        # ── CONFIRMING ───────────────────────────────────────────────────────
        if state.step == ConversationStep.CONFIRMING:
            positive = {"si", "sí", "yes", "ok", "dale", "claro", "confirmo", "listo"}
            if t in positive or any(p in t for p in positive):
                self._create_appointment(client, state, business)
            else:
                self._reset_state(state)
                self.session.commit()
                self._send(client.phone, MSG.BOOKING_CANCELLED)
            return

    def _start_booking(
        self,
        client: Client,
        state: ConversationState,
        business: Business,
    ) -> None:
        """Inicia el flujo de agendamiento."""
        schedule = self._get_schedule(business.id)
        if not schedule:
            self._send(client.phone,
                "¡Hola! Por ahora el agendamiento no está disponible. "
                "Contáctanos directamente para reservar tu cita. 🙏")
            return

        services = self._get_active_services(business.id)
        if not services:
            self._send(client.phone,
                "¡Hola! En este momento no tenemos servicios disponibles para agendar. "
                "Contáctanos para más información. 🙏")
            return

        state.step = ConversationStep.SELECTING_SERVICE
        state.context_data = {}
        state.last_activity = datetime.utcnow()
        self.session.commit()

        self._send(client.phone,
            build_service_selection_message(services))

    def _create_appointment(
        self,
        client: Client,
        state: ConversationState,
        business: Business,
    ) -> None:
        """Crea la cita en base de datos y notifica al negocio."""
        from app.services.notifications import create_notification_sync
        from app.models.notification import NotificationType

        ctx = state.context_data
        chosen_date = date.fromisoformat(ctx["appointment_date"])
        service_id = ctx["service_id"]
        appointment_time = ctx.get("appointment_time")
        shift_str = ctx.get("shift")

        # Importar AppointmentShift aquí para evitar circular
        from app.models.appointment import AppointmentShift
        shift = AppointmentShift(shift_str) if shift_str else None

        appointment = Appointment(
            business_id=business.id,
            client_id=client.id,
            service_id=service_id,
            status=AppointmentStatus.REQUESTED,
            appointment_date=chosen_date,
            appointment_time=appointment_time,
            shift=shift,
        )
        self.session.add(appointment)

        # Marcar conversación como completada
        state.step = ConversationStep.COMPLETED
        state.last_activity = datetime.utcnow()

        # Notificar al negocio
        service_name = ctx.get("service_name", "—")
        day_name = DAY_NAMES[chosen_date.weekday()]
        month = MONTH_NAMES[chosen_date.month]
        date_str = f"{day_name} {chosen_date.day} {month}"
        time_str = _format_time_display(state)

        create_notification_sync(
            self.session,
            business.id,
            NotificationType.APPOINTMENT_REQUESTED,
            f"Nueva cita solicitada: {client.display_name}",
            f"{client.display_name} quiere agendar *{service_name}* el {date_str} ({time_str}).",
        )

        self.session.commit()

        # Confirmar al cliente
        self._send(client.phone, MSG.BOOKING_CREATED.format(
            business=business.name,
            service=service_name,
            date=date_str,
            time=time_str,
        ))

        logger.info(
            f"[chatbot] Cita creada: client={client.id} "
            f"service={service_id} date={chosen_date}"
        )
