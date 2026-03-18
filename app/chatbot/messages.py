"""
Textos de los mensajes del chatbot.
Centralizados aquí para facilitar traducción y mantenimiento.
"""

GREETING = (
    "¡Hola {name}! 👋 Soy el asistente de *{business}*.\n\n"
    "¿Te gustaría agendar una cita? Responde *SI* para comenzar "
    "o *NO* si solo quieres chatear."
)

SHOW_SERVICES = (
    "¡Perfecto! ¿Qué servicio deseas agendar?\n\n"
    "{service_list}\n\n"
    "Responde con el *número* de tu elección."
)

SERVICE_NOT_FOUND = (
    "No entendí tu elección 🤔. Por favor responde con el número del servicio:\n\n"
    "{service_list}"
)

ASK_DATE = (
    "¡Excelente! Has elegido *{service}*.\n\n"
    "¿Qué día prefieres?\n\n"
    "{date_list}\n\n"
    "Responde con el *número* del día o escribe la fecha (ej: *25 marzo*)."
)

DATE_NOT_FOUND = (
    "No reconocí esa fecha 📅. Por favor elige una opción:\n\n"
    "{date_list}\n\n"
    "O escribe la fecha así: *25 marzo*"
)

DATE_NOT_AVAILABLE = (
    "Lo siento, ese día no tenemos disponibilidad 😔.\n\n"
    "Elige otro día:\n\n"
    "{date_list}"
)

# Para modo time_slots
ASK_TIME = (
    "¿A qué hora te queda mejor el *{date}*?\n\n"
    "{slot_list}\n\n"
    "Responde con el *número* de tu preferencia."
)

SLOT_NOT_FOUND = (
    "No reconocí ese horario ⏰. Por favor elige uno:\n\n"
    "{slot_list}"
)

# Para modo capacity
ASK_SHIFT = (
    "¿En qué turno prefieres el *{date}*?\n\n"
    "1️⃣ Mañana (8am - 12pm)\n"
    "2️⃣ Tarde (1pm - 5pm)\n"
    "3️⃣ Noche (5pm - 8pm)\n\n"
    "Responde con el *número*."
)

SHIFT_NOT_FOUND = (
    "No reconocí ese turno. Por favor elige:\n\n"
    "1️⃣ Mañana\n2️⃣ Tarde\n3️⃣ Noche"
)

CONFIRM_BOOKING = (
    "¡Casi listo! 🎉 Confirma tu cita:\n\n"
    "📋 *Servicio:* {service}\n"
    "📅 *Fecha:* {date}\n"
    "⏰ *Hora/Turno:* {time}\n\n"
    "Responde *SI* para confirmar o *NO* para cancelar."
)

BOOKING_CREATED = (
    "✅ ¡Tu solicitud fue registrada!\n\n"
    "*{business}* revisará tu cita y te confirmará pronto.\n\n"
    "📋 *Servicio:* {service}\n"
    "📅 *Fecha:* {date}\n"
    "⏰ *Hora/Turno:* {time}\n\n"
    "Te avisamos cuando esté confirmada. ¡Hasta pronto! 👋"
)

BOOKING_CANCELLED = (
    "Entendido, hemos cancelado tu solicitud. "
    "Cuando quieras agendar, escríbenos. 😊"
)

APPOINTMENT_CONFIRMED_CLIENT = (
    "✅ *¡Tu cita está confirmada!*\n\n"
    "📋 *Servicio:* {service}\n"
    "📅 *Fecha:* {date}\n"
    "⏰ *Hora/Turno:* {time}\n\n"
    "Te esperamos en *{business}*. ¡Hasta pronto! 👋"
)

APPOINTMENT_REJECTED_CLIENT = (
    "Lo sentimos 😔, no pudimos confirmar tu cita para el {date}.\n\n"
    "Escríbenos para buscar otro horario disponible. 🙏"
)

APPOINTMENT_REMINDER_CLIENT = (
    "⏰ *Recordatorio de cita*\n\n"
    "Hola {name}, te recordamos tu cita en *{business}* mañana:\n\n"
    "📋 *Servicio:* {service}\n"
    "📅 *Fecha:* {date}\n"
    "⏰ *Hora/Turno:* {time}\n\n"
    "¿Confirmas tu asistencia? Responde *SI* o *NO*."
)

UNKNOWN_RESPONSE = (
    "No entendí tu mensaje 🤔. "
    "Si deseas agendar una cita escribe *CITA* o *AGENDAR*."
)

OPTOUT_CONFIRMED = (
    "Listo {name}, no recibirás más mensajes de *{business}*. "
    "Si cambias de opinión, escríbenos. ¡Hasta pronto!"
)
