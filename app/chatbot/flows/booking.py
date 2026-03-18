"""
Flujo de agendamiento de citas (booking flow).

Gestiona las transiciones de estado y genera los mensajes
para cada paso del proceso de agendamiento.
"""
import logging
import unicodedata
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus, AppointmentShift
from app.models.conversation_state import ConversationState, ConversationStep
from app.models.business_schedule import BusinessSchedule, ScheduleMode
from app.models.service import Service
from app.chatbot import messages as MSG

logger = logging.getLogger(__name__)

# Mapeo de nombres de días al español
DAY_NAMES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}
MONTH_NAMES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"
}
MONTH_FULL = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12, "ene": 1, "feb": 2, "mar": 3, "abr": 4,
    "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10,
    "nov": 11, "dic": 12,
}

SHIFT_MAP = {
    "1": AppointmentShift.MORNING,
    "2": AppointmentShift.AFTERNOON,
    "3": AppointmentShift.EVENING,
    "mañana": AppointmentShift.MORNING,
    "manana": AppointmentShift.MORNING,
    "tarde": AppointmentShift.AFTERNOON,
    "noche": AppointmentShift.EVENING,
}

SHIFT_LABELS = {
    AppointmentShift.MORNING:   "Mañana (8am - 12pm)",
    AppointmentShift.AFTERNOON: "Tarde (1pm - 5pm)",
    AppointmentShift.EVENING:   "Noche (5pm - 8pm)",
}


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas, sin acentos."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _get_available_dates(schedule: BusinessSchedule, max_days: int = 7) -> list[date]:
    """
    Retorna los próximos días disponibles según el horario del negocio.
    Busca hasta max_days días hacia adelante.
    """
    day_key_map = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }
    available = []
    today = date.today()
    for i in range(1, schedule.max_days_ahead + 1):
        candidate = today + timedelta(days=i)
        day_key = day_key_map[candidate.weekday()]
        day_data = schedule.schedule_data.get(day_key, {})
        if day_data:  # Si hay slots o capacidad para ese día
            available.append(candidate)
        if len(available) >= max_days:
            break
    return available


def _format_date_list(dates: list[date]) -> str:
    """Formatea la lista de fechas disponibles para mostrar al cliente."""
    lines = []
    for i, d in enumerate(dates, 1):
        day_name = DAY_NAMES[d.weekday()]
        month = MONTH_NAMES[d.month]
        lines.append(f"{i}️⃣ {day_name} {d.day} {month}")
    return "\n".join(lines)


def _parse_date_choice(text: str, available_dates: list[date]) -> date | None:
    """
    Intenta parsear la elección de fecha del usuario.
    Acepta: número (1, 2, ...) o texto como "25 marzo".
    """
    t = _normalize(text)

    # Intento por número
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < len(available_dates):
            return available_dates[idx]
        return None

    # Intento por "día mes" (ej: "25 marzo", "5 abr")
    parts = t.split()
    if len(parts) >= 2:
        try:
            day_num = int(parts[0])
            month_name = parts[1]
            month_num = MONTH_FULL.get(month_name)
            if month_num:
                year = date.today().year
                candidate = date(year, month_num, day_num)
                if candidate in available_dates:
                    return candidate
        except (ValueError, TypeError):
            pass

    return None


def _get_available_slots(schedule: BusinessSchedule, chosen_date: date) -> list[str]:
    """Retorna los slots disponibles para una fecha dada (mode=time_slots)."""
    day_key_map = {
        0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
        4: "friday", 5: "saturday", 6: "sunday"
    }
    day_key = day_key_map[chosen_date.weekday()]
    return schedule.schedule_data.get(day_key, [])


def _format_slot_list(slots: list[str]) -> str:
    lines = [f"{i}️⃣ {s}" for i, s in enumerate(slots, 1)]
    return "\n".join(lines)


def _parse_slot_choice(text: str, slots: list[str]) -> str | None:
    t = _normalize(text)
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < len(slots):
            return slots[idx]
    # Intento por texto exacto
    for slot in slots:
        if _normalize(slot) == t:
            return slot
    return None


def _format_time_display(state: ConversationState) -> str:
    """Formatea hora/turno para mostrar en el resumen de confirmación."""
    ctx = state.context_data
    if ctx.get("appointment_time"):
        return ctx["appointment_time"]
    shift = ctx.get("shift")
    if shift:
        return SHIFT_LABELS.get(AppointmentShift(shift), shift)
    return "—"


# ─── HANDLERS DE CADA PASO ───────────────────────────────────────────────────

def handle_selecting_service(
    text: str,
    state: ConversationState,
    services: list[Service],
) -> str:
    """Procesa la elección de servicio. Retorna mensaje de respuesta."""
    t = _normalize(text)

    chosen = None
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < len(services):
            chosen = services[idx]

    if not chosen:
        # Buscar por nombre
        for svc in services:
            if _normalize(svc.name) in t or t in _normalize(svc.name):
                chosen = svc
                break

    if not chosen:
        service_list = _build_service_list(services)
        return MSG.SERVICE_NOT_FOUND.format(service_list=service_list)

    # Guardar servicio elegido y avanzar al paso de fecha
    state.context_data = {**state.context_data, "service_id": str(chosen.id), "service_name": chosen.name}
    state.step = ConversationStep.SELECTING_DATE
    state.last_activity = datetime.utcnow()
    return ""  # El engine generará el mensaje de fecha


def handle_selecting_date(
    text: str,
    state: ConversationState,
    schedule: BusinessSchedule,
) -> tuple[str, date | None]:
    """Procesa la elección de fecha. Retorna (mensaje, fecha elegida | None)."""
    available = _get_available_dates(schedule)

    if not available:
        return "Lo siento, no hay fechas disponibles en este momento. Escríbenos para más información.", None

    chosen = _parse_date_choice(text, available)
    if not chosen:
        return MSG.DATE_NOT_FOUND.format(date_list=_format_date_list(available)), None

    return "", chosen


def handle_selecting_slot(
    text: str,
    state: ConversationState,
    schedule: BusinessSchedule,
    chosen_date: date,
) -> str:
    """Procesa la elección de hora/turno. Retorna mensaje de error o '' si OK."""
    if schedule.mode == ScheduleMode.TIME_SLOTS:
        slots = _get_available_slots(schedule, chosen_date)
        slot = _parse_slot_choice(text, slots)
        if not slot:
            return MSG.SLOT_NOT_FOUND.format(slot_list=_format_slot_list(slots))
        state.context_data = {**state.context_data, "appointment_time": slot}
    else:
        # capacity mode
        t = _normalize(text)
        shift = SHIFT_MAP.get(t)
        if not shift:
            return MSG.SHIFT_NOT_FOUND
        state.context_data = {**state.context_data, "shift": shift.value}

    state.step = ConversationStep.CONFIRMING
    state.last_activity = datetime.utcnow()
    return ""


def build_confirmation_message(state: ConversationState) -> str:
    ctx = state.context_data
    chosen_date = date.fromisoformat(ctx["appointment_date"])
    day_name = DAY_NAMES[chosen_date.weekday()]
    month = MONTH_NAMES[chosen_date.month]
    date_str = f"{day_name} {chosen_date.day} {month}"
    time_str = _format_time_display(state)
    return MSG.CONFIRM_BOOKING.format(
        service=ctx.get("service_name", "—"),
        date=date_str,
        time=time_str,
    )


def _build_service_list(services: list[Service]) -> str:
    lines = []
    for i, svc in enumerate(services, 1):
        price = f" (${svc.ref_price:,.0f})" if svc.ref_price else ""
        lines.append(f"{i}️⃣ {svc.name}{price}")
    return "\n".join(lines)


def build_service_selection_message(services: list[Service]) -> str:
    return MSG.SHOW_SERVICES.format(service_list=_build_service_list(services))


def build_date_selection_message(service_name: str, schedule: BusinessSchedule) -> str:
    available = _get_available_dates(schedule)
    return MSG.ASK_DATE.format(
        service=service_name,
        date_list=_format_date_list(available),
    )


def build_slot_selection_message(chosen_date: date, schedule: BusinessSchedule) -> str:
    day_name = DAY_NAMES[chosen_date.weekday()]
    month = MONTH_NAMES[chosen_date.month]
    date_str = f"{day_name} {chosen_date.day} {month}"

    if schedule.mode == ScheduleMode.TIME_SLOTS:
        slots = _get_available_slots(schedule, chosen_date)
        return MSG.ASK_TIME.format(
            date=date_str,
            slot_list=_format_slot_list(slots),
        )
    else:
        return MSG.ASK_SHIFT.format(date=date_str)
