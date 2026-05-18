"""
Anti no-show: ciclo de confirmación obligatoria 2h antes.

Beat ejecuta cada 15 min:
  - request_confirmations: encuentra citas CONFIRMED cuya hora caiga
    dentro de la ventana `lead_minutes` y aún no se ha pedido confirmación.
    Envía WhatsApp "¿confirmas?" y mueve a AWAITING_CONFIRMATION.

Beat ejecuta cada 5 min:
  - expire_unconfirmed: citas AWAITING_CONFIRMATION con
    `confirmation_requested_at` > `window_minutes` sin respuesta del cliente
    se auto-cancelan y disparan matcher de waitlist.

No reintenta automáticamente — cualquier fallo Twilio queda registrado y
la cita se procesará en la siguiente corrida.
"""
import logging
from datetime import datetime, timedelta, time as time_cls
from typing import Iterable

from sqlalchemy import select, and_

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session

logger = logging.getLogger(__name__)


def _appointment_datetime(appt) -> datetime | None:
    """Combina appointment_date + appointment_time/shift en un datetime."""
    if appt.appointment_time:
        try:
            hh, mm = str(appt.appointment_time)[:5].split(":")
            return datetime.combine(appt.appointment_date, time_cls(int(hh), int(mm)))
        except Exception:
            pass
    # Si solo hay shift, asumimos un default por turno
    shift_default = {"morning": time_cls(9, 0), "afternoon": time_cls(14, 0), "evening": time_cls(18, 0)}
    if appt.shift:
        key = appt.shift.value if hasattr(appt.shift, "value") else str(appt.shift)
        return datetime.combine(appt.appointment_date, shift_default.get(key, time_cls(12, 0)))
    return datetime.combine(appt.appointment_date, time_cls(12, 0))


@celery_app.task(name="app.tasks.appointment_confirmations.request_confirmations")
def request_confirmations():
    """
    Encuentra citas CONFIRMED próximas y manda "¿confirmas?".
    """
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.business import Business
    from app.models.client import Client, ClientStatus
    from app.models.service import Service
    from app.messaging import get_messaging_provider
    from app.services.messaging_format import prefix_business

    session = get_sync_session()
    sent = 0
    try:
        now = datetime.utcnow()
        # Ventana amplia: buscamos citas en los próximos 4h, luego filtramos por lead específico.
        cutoff = now + timedelta(hours=4)
        candidates = (
            session.query(Appointment)
            .filter(
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.confirmation_requested_at.is_(None),
                Appointment.appointment_date >= now.date(),
                Appointment.appointment_date <= cutoff.date(),
            )
            .all()
        )
        if not candidates:
            return {"checked": 0, "sent": 0}

        provider = get_messaging_provider()
        for appt in candidates:
            biz = session.get(Business, appt.business_id)
            if not biz or not biz.require_confirmation:
                continue
            appt_dt = _appointment_datetime(appt)
            if not appt_dt:
                continue
            lead = biz.confirmation_lead_minutes or 120
            # solo si la cita está a <= lead minutos
            if appt_dt - now > timedelta(minutes=lead):
                continue
            # si ya pasó la cita, skip
            if appt_dt < now:
                continue

            client = session.get(Client, appt.client_id)
            if not client or client.status == ClientStatus.OPTOUT:
                continue

            service = session.get(Service, appt.service_id) if appt.service_id else None
            service_name = service.name if service else "tu cita"
            time_label = (
                str(appt.appointment_time)[:5]
                if appt.appointment_time else (appt.shift.value if appt.shift else "")
            )

            body = (
                f"Hola {client.display_name}, te recordamos tu cita de "
                f"*{service_name}* hoy a las *{time_label}*.\n\n"
                f"¿Confirmas que vienes? Responde *SI* o *NO*.\n"
                f"_Si no respondes en {biz.confirmation_window_minutes or 30} min "
                f"liberamos el cupo para otra persona._"
            )
            body = prefix_business(biz.name, body)
            res = provider.send_text(to=client.phone, body=body)
            if res.success:
                appt.status = AppointmentStatus.AWAITING_CONFIRMATION
                appt.confirmation_requested_at = now
                session.flush()
                sent += 1
                logger.info(f"[confirm] solicitud enviada a appt={appt.id} client={client.id}")
            else:
                logger.warning(f"[confirm] envío falló appt={appt.id}: {res.error}")

        session.commit()
        return {"checked": len(candidates), "sent": sent}
    except Exception as exc:
        session.rollback()
        logger.exception(f"[confirm] error en request_confirmations: {exc}")
        return {"error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="app.tasks.appointment_confirmations.expire_unconfirmed")
def expire_unconfirmed():
    """
    Citas AWAITING_CONFIRMATION sin respuesta tras `window_minutes` →
    auto-cancela y dispara waitlist.
    """
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.business import Business

    session = get_sync_session()
    cancelled = 0
    try:
        now = datetime.utcnow()
        candidates = (
            session.query(Appointment)
            .filter(
                Appointment.status == AppointmentStatus.AWAITING_CONFIRMATION,
                Appointment.confirmation_requested_at.is_not(None),
            )
            .all()
        )
        if not candidates:
            return {"cancelled": 0}

        from app.tasks.waitlist_matching import process_waitlist_for_appointment_task
        for appt in candidates:
            biz = session.get(Business, appt.business_id)
            window = (biz.confirmation_window_minutes if biz else 30) or 30
            if now - appt.confirmation_requested_at < timedelta(minutes=window):
                continue
            appt.status = AppointmentStatus.CANCELLED
            session.flush()
            cancelled += 1
            # Encolar matcher de waitlist
            try:
                process_waitlist_for_appointment_task.delay(str(appt.id))
            except Exception as exc:
                logger.warning(f"[confirm] no se pudo encolar waitlist: {exc}")
            logger.info(f"[confirm] auto-cancel appt={appt.id} por no confirmación")
        session.commit()
        return {"cancelled": cancelled}
    except Exception as exc:
        session.rollback()
        logger.exception(f"[confirm] error en expire_unconfirmed: {exc}")
        return {"error": str(exc)}
    finally:
        session.close()
