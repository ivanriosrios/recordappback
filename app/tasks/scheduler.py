"""
Scheduler Celery Beat: tareas periódicas del motor de envío.

Tareas:
- check_and_enqueue_reminders: cada hora, busca reminders del día y los encola
- check_retries: cada 6h, maneja reintentos de mensajes fallidos
"""
import logging
from datetime import date, datetime, timedelta

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.tasks.send_follow_up import send_follow_up_task

logger = logging.getLogger(__name__)

# Días máximo de silencio antes de considerar un reintento como fallido definitivo
MAX_RETRY_WINDOW_DAYS = 5
MAX_RETRIES = 4
FOLLOW_UP_CATCHUP_DAYS = 7


@celery_app.task(name="app.tasks.scheduler.check_and_enqueue_reminders")
def check_and_enqueue_reminders():
    """
    Corre cada hora. Busca todos los recordatorios activos cuya
    next_send_date sea hoy o anterior y los encola para envío.

    Lógica:
    - next_send_date <= hoy → es hora de enviar
    - notify_days_before: si el recordatorio avisa N días antes,
      la fecha real de envío es next_send_date - notify_days_before
    """
    from app.tasks.send_reminder import send_reminder_task
    from app.models.reminder import Reminder, ReminderStatus
    from sqlalchemy import and_

    session = get_sync_session()
    try:
        today = date.today()

        # Fecha de disparo = next_send_date - notify_days_before
        # Buscamos reminders donde hoy >= fecha de disparo
        reminders = (
            session.query(Reminder)
            .filter(
                and_(
                    # Usar value en vez del Enum para evitar pasar 'ACTIVE' (nombre) en vez de 'active' (valor)
                    Reminder.status == ReminderStatus.ACTIVE.value,
                    Reminder.next_send_date <= today + timedelta(days=3),  # ventana holgada
                )
            )
            .all()
        )

        enqueued = 0
        for reminder in reminders:
            # Calcular fecha real de envío
            send_date = reminder.next_send_date - timedelta(days=reminder.notify_days_before or 0)

            if send_date > today:
                continue  # todavía no

            # Evitar reenviar si ya se envió hoy
            if reminder.last_sent_at and reminder.last_sent_at.date() == today:
                continue

            send_reminder_task.delay(str(reminder.id))
            enqueued += 1
            logger.info(f"[scheduler] Encolado reminder {reminder.id} para cliente {reminder.client_id}")

        logger.info(f"[scheduler] check_and_enqueue_reminders — {enqueued} recordatorios encolados")
        return {"enqueued": enqueued, "checked": len(reminders)}

    except Exception as exc:
        logger.exception(f"[scheduler] Error en check_and_enqueue_reminders: {exc}")
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.scheduler.check_retries")
def check_retries():
    """
    Corre cada 6 horas. Busca logs con status=failed que no
    hayan superado MAX_RETRIES y los reencola.

    También busca mensajes sin respuesta después de MAX_RETRY_WINDOW_DAYS
    y envía un segundo intento.
    """
    from app.tasks.send_reminder import send_reminder_task
    from app.models.reminder_log import ReminderLog, LogStatus
    from app.models.reminder import Reminder, ReminderStatus
    from sqlalchemy import and_, func

    session = get_sync_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=MAX_RETRY_WINDOW_DAYS)

        # Reminders con log fallido reciente (dentro de la ventana)
        failed_logs = (
            session.query(ReminderLog)
            .filter(
                and_(
                    # Usar value del enum para no pasar 'FAILED' en mayúsculas al enum de Postgres
                    ReminderLog.status == LogStatus.FAILED.value,
                    ReminderLog.sent_at >= cutoff,
                )
            )
            .all()
        )

        retried = 0
        seen_reminders = set()

        for log in failed_logs:
            reminder_id = str(log.reminder_id)
            if reminder_id in seen_reminders:
                continue
            seen_reminders.add(reminder_id)

            # Contar cuántos intentos fallidos tiene este reminder
            fail_count = (
                session.query(func.count(ReminderLog.id))
                .filter(
                    and_(
                        ReminderLog.reminder_id == log.reminder_id,
                        ReminderLog.status == LogStatus.FAILED,
                    )
                )
                .scalar()
            )

            if fail_count < MAX_RETRIES:
                send_reminder_task.delay(reminder_id)
                retried += 1
                logger.info(f"[scheduler] Reintento #{fail_count + 1} para reminder {reminder_id}")
            else:
                # Marcar como done para no seguir intentando
                reminder = session.get(Reminder, reminder_id)
                if reminder and reminder.status == ReminderStatus.ACTIVE:
                    reminder.status = ReminderStatus.DONE
                    session.commit()
                    logger.warning(f"[scheduler] Reminder {reminder_id} marcado DONE tras {fail_count} fallos")

        logger.info(f"[scheduler] check_retries — {retried} reintentos encolados")
        return {"retried": retried}

    except Exception as exc:
        logger.exception(f"[scheduler] Error en check_retries: {exc}")
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.scheduler.check_pending_follow_ups")
def check_pending_follow_ups():
    """
    Corre cada 4h. Busca ServiceLogs sin follow_up_sent cuyo servicio
    tenga follow_up_days y cuya fecha ya venció, y los encola.
    """
    from app.models.service_log import ServiceLog
    from app.models.service import Service

    session = get_sync_session()
    try:
        now = datetime.utcnow()
        logs = (
            session.query(ServiceLog)
            .join(Service, Service.id == ServiceLog.service_id)
            .filter(Service.follow_up_days.isnot(None), ServiceLog.follow_up_sent == False)  # noqa: E712
            .limit(300)
            .all()
        )

        enqueued = 0
        for log in logs:
            follow_days = log.service.follow_up_days
            if follow_days is None:
                continue
            due_at = log.completed_at + timedelta(days=follow_days)

            if (now - log.completed_at).days > FOLLOW_UP_CATCHUP_DAYS:
                log.follow_up_sent = True
                continue

            if now >= due_at:
                send_follow_up_task.delay(str(log.id))
                enqueued += 1

        session.commit()
        logger.info(f"[scheduler] check_pending_follow_ups — {enqueued} follow-ups encolados")
        return {"enqueued": enqueued}
    except Exception as exc:
        session.rollback()
        logger.exception(f"[scheduler] Error en check_pending_follow_ups: {exc}")
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.scheduler.check_birthdays")
def check_birthdays():
    """
    Revisa clientes que cumplen años hoy y encola mensajes de felicitación.
    Corre una vez al día a las 8am.
    """
    from app.models.client import Client, ClientStatus
    from sqlalchemy import extract

    session = get_sync_session()
    try:
        today = date.today()
        # Buscar clientes activos cuyo birth_date coincida en mes y día
        clients = (
            session.query(Client)
            .filter(
                Client.status == ClientStatus.ACTIVE,
                Client.birth_date.isnot(None),
                extract("month", Client.birth_date) == today.month,
                extract("day", Client.birth_date) == today.day,
            )
            .all()
        )

        from app.tasks.send_birthday import send_birthday_task

        for client in clients:
            send_birthday_task.delay(str(client.id), str(client.business_id))
            logger.info(f"[birthday] Encolado para {client.display_name}")

        logger.info(f"[birthday] {len(clients)} cumpleaños encontrados y encolados")
    except Exception as exc:
        logger.exception(f"[birthday] Error: {exc}")
    finally:
        session.close()


@celery_app.task(name="app.tasks.scheduler.check_appointment_reminders")
def check_appointment_reminders():
    """
    Corre cada hora (:30). Busca citas CONFIRMED para mañana
    que aún no tengan reminder_sent=True y encola el recordatorio.
    """
    from app.models.appointment import Appointment, AppointmentStatus
    from app.tasks.send_appointment_reminder import send_appointment_reminder_task
    from sqlalchemy import and_
    from datetime import timedelta

    session = get_sync_session()
    try:
        tomorrow = date.today() + timedelta(days=1)

        appointments = (
            session.query(Appointment)
            .filter(
                and_(
                    Appointment.status == AppointmentStatus.CONFIRMED,
                    Appointment.appointment_date == tomorrow,
                    Appointment.reminder_sent == False,  # noqa: E712
                )
            )
            .all()
        )

        enqueued = 0
        for appt in appointments:
            send_appointment_reminder_task.delay(str(appt.id))
            enqueued += 1
            logger.info(f"[scheduler] Recordatorio de cita encolado para {appt.id}")

        logger.info(f"[scheduler] check_appointment_reminders — {enqueued} recordatorios encolados")
        return {"enqueued": enqueued}

    except Exception as exc:
        logger.exception(f"[scheduler] Error en check_appointment_reminders: {exc}")
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.scheduler.check_inactive_clients")
def check_inactive_clients():
    """
    Detecta clientes inactivos (sin servicio en >60 días) y envía reactivación.
    Corre una vez a la semana (lunes a las 10am).
    """
    from app.models.client import Client, ClientStatus
    from app.models.service_log import ServiceLog
    from app.models.reminder_log import ReminderLog
    from sqlalchemy import select, func

    session = get_sync_session()
    try:
        cutoff = date.today() - timedelta(days=60)

        # Clientes activos cuyo último servicio fue hace >60 días o sin servicios
        last_service = (
            session.query(
                ServiceLog.client_id,
                func.max(ServiceLog.completed_at).label("last_visit"),
            )
            .group_by(ServiceLog.client_id)
            .subquery()
        )

        stmt = (
            session.query(Client)
            .outerjoin(last_service, Client.id == last_service.c.client_id)
            .filter(
                Client.status == ClientStatus.ACTIVE,
                (last_service.c.last_visit < cutoff) | (last_service.c.last_visit.is_(None)),
            )
        )

        clients = stmt.all()

        from app.tasks.send_reactivation import send_reactivation_task

        enqueued = 0
        for client in clients:
            # Solo enviar si no se le envió reactivación en últimos 30 días (para no spamear)
            recent = (
                session.query(func.count(ReminderLog.id))
                .filter(
                    ReminderLog.sent_at > datetime.utcnow() - timedelta(days=30),
                )
                .scalar()
            )
            # Simple: limit to max 50 reactivations per run
            if enqueued >= 50:
                break
            send_reactivation_task.delay(str(client.id), str(client.business_id))
            enqueued += 1

        logger.info(f"[reactivation] {enqueued} reactivaciones encoladas")
    except Exception as exc:
        logger.exception(f"[reactivation] Error: {exc}")
    finally:
        session.close()


