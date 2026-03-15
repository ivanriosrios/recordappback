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
