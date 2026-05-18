"""
Sustitución automática vía waitlist.

Cuando una cita se libera (CANCELLED, NO_SHOW, auto-cancel por no confirmar),
encontramos el primer cliente en waitlist que coincide por servicio +
preferencias y le ofrecemos el slot por WhatsApp.

Si el cliente responde SI dentro de la ventana de oferta (60 min default),
se crea Appointment con rescued_from_waitlist=True y la entrada queda
ACCEPTED. Si no responde o dice NO, se ofrece al siguiente.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, asc

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session

logger = logging.getLogger(__name__)

OFFER_TTL_MINUTES = 60


@celery_app.task(name="app.tasks.waitlist_matching.process_waitlist_for_appointment_task")
def process_waitlist_for_appointment_task(appointment_id: str):
    """
    Busca match en waitlist y le ofrece el slot al primero de la cola.
    """
    from app.models.appointment import Appointment
    from app.models.business import Business
    from app.models.client import Client, ClientStatus
    from app.models.service import Service
    from app.models.waitlist import WaitlistEntry, WaitlistStatus
    from app.messaging import get_messaging_provider
    from app.services.messaging_format import prefix_business

    session = get_sync_session()
    try:
        appt = session.get(Appointment, appointment_id)
        if not appt:
            return {"error": "appointment_not_found"}

        # Filtros por servicio + fecha preferida (si la entrada la tiene)
        q = (
            session.query(WaitlistEntry)
            .filter(
                WaitlistEntry.business_id == appt.business_id,
                WaitlistEntry.service_id == appt.service_id,
                WaitlistEntry.status == WaitlistStatus.PENDING,
            )
            .order_by(asc(WaitlistEntry.created_at))
        )
        candidates = q.all()

        chosen = None
        for entry in candidates:
            if entry.preferred_date and entry.preferred_date != appt.appointment_date:
                continue
            if entry.preferred_shift and appt.shift and entry.preferred_shift != appt.shift:
                continue
            chosen = entry
            break

        if not chosen:
            logger.info(f"[waitlist] sin match para appt={appointment_id}")
            return {"matched": False}

        client = session.get(Client, chosen.client_id)
        if not client or client.status == ClientStatus.OPTOUT:
            chosen.status = WaitlistStatus.DECLINED
            session.commit()
            # Intentar con el siguiente
            process_waitlist_for_appointment_task.delay(appointment_id)
            return {"skipped": "opted_out", "next": True}

        biz = session.get(Business, appt.business_id)
        service = session.get(Service, appt.service_id) if appt.service_id else None
        service_name = service.name if service else "el servicio"

        time_label = (
            str(appt.appointment_time)[:5]
            if appt.appointment_time else (appt.shift.value if appt.shift else "")
        )

        body = (
            f"Hola {client.display_name}, se liberó un cupo de "
            f"*{service_name}* el *{appt.appointment_date}* a las *{time_label}*.\n\n"
            f"¿Lo tomas? Responde *SI* o *NO* en los próximos 60 min."
        )
        body = prefix_business(biz.name if biz else None, body)

        provider = get_messaging_provider()
        res = provider.send_text(to=client.phone, body=body)
        if not res.success:
            logger.warning(f"[waitlist] envío falló a client={client.id}: {res.error}")
            return {"sent": False}

        chosen.status = WaitlistStatus.OFFERED
        chosen.offered_appointment_id = appt.id
        chosen.offered_at = datetime.utcnow()
        chosen.expires_at = datetime.utcnow() + timedelta(minutes=OFFER_TTL_MINUTES)
        session.commit()
        logger.info(
            f"[waitlist] cupo ofrecido a client={client.id} entry={chosen.id} appt={appt.id}"
        )
        return {"matched": True, "entry_id": str(chosen.id)}
    except Exception as exc:
        session.rollback()
        logger.exception(f"[waitlist] error: {exc}")
        return {"error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="app.tasks.waitlist_matching.expire_offers_task")
def expire_offers_task():
    """
    Expira ofertas no respondidas en la ventana y reintenta con el
    siguiente en la cola.
    """
    from app.models.waitlist import WaitlistEntry, WaitlistStatus

    session = get_sync_session()
    expired = 0
    try:
        now = datetime.utcnow()
        rows = (
            session.query(WaitlistEntry)
            .filter(
                WaitlistEntry.status == WaitlistStatus.OFFERED,
                WaitlistEntry.expires_at.is_not(None),
                WaitlistEntry.expires_at < now,
            )
            .all()
        )
        retry_appts: set[str] = set()
        for entry in rows:
            entry.status = WaitlistStatus.EXPIRED
            if entry.offered_appointment_id:
                retry_appts.add(str(entry.offered_appointment_id))
            expired += 1
        session.commit()
        for appt_id in retry_appts:
            try:
                process_waitlist_for_appointment_task.delay(appt_id)
            except Exception as exc:
                logger.warning(f"[waitlist] no se pudo re-encolar appt={appt_id}: {exc}")
        return {"expired": expired, "retried": len(retry_appts)}
    except Exception as exc:
        session.rollback()
        logger.exception(f"[waitlist] expire error: {exc}")
        return {"error": str(exc)}
    finally:
        session.close()
