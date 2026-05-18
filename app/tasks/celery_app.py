"""
Configuración de Celery con Redis como broker y backend.
"""
import logging

from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Sentry para los workers (opcional)
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[CeleryIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )
        logger.info("[sentry] inicializado en worker Celery")
    except Exception as exc:
        logger.warning(f"[sentry] no se pudo inicializar en Celery: {exc}")

celery_app = Celery(
    "recordapp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.send_reminder",
        "app.tasks.send_follow_up",
        "app.tasks.send_birthday",
        "app.tasks.send_reactivation",
        "app.tasks.send_appointment_reminder",
        "app.tasks.send_service_summary",
        "app.tasks.notify_pending_appointments",
        "app.tasks.scheduler",
        "app.tasks.appointment_confirmations",
        "app.tasks.waitlist_matching",
    ],
)

celery_app.conf.update(
    # Conexión al broker — resiliente a reinicios de Redis
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,

    # Reintentos automáticos
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,

    # Celery Beat — tareas periódicas
    beat_schedule={
        # Cada hora revisa qué recordatorios hay que enviar hoy
        "check-reminders-hourly": {
            "task": "app.tasks.scheduler.check_and_enqueue_reminders",
            "schedule": crontab(minute=0),           # cada hora en punto
        },
        # Cada 6 horas chequea reintentos pendientes
        "check-retries": {
            "task": "app.tasks.scheduler.check_retries",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Cada 4 horas revisa follow-ups pendientes por enviar
        "check-pending-follow-ups": {
            "task": "app.tasks.scheduler.check_pending_follow_ups",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        # Cada día a las 8am revisa cumpleaños
        "check-birthdays": {
            "task": "app.tasks.scheduler.check_birthdays",
            "schedule": crontab(hour=8, minute=0),
        },
        # Cada lunes a las 10am revisa clientes inactivos
        "check-inactive-clients": {
            "task": "app.tasks.scheduler.check_inactive_clients",
            "schedule": crontab(hour=10, minute=0, day_of_week=1),
        },
        # Cada hora revisa citas confirmadas para mañana y envía recordatorio
        "check-appointment-reminders": {
            "task": "app.tasks.scheduler.check_appointment_reminders",
            "schedule": crontab(minute=30),   # :30 de cada hora
        },
        # Cada 2h alerta al negocio sobre citas sin confirmar
        "check-pending-appointments": {
            "task": "app.tasks.notify_pending_appointments.notify_pending_appointments_task",
            "schedule": crontab(minute=0, hour="*/2"),
        },
        # Anti no-show: pedir confirmación al cliente ~2h antes de la cita
        "request-appointment-confirmations": {
            "task": "app.tasks.appointment_confirmations.request_confirmations",
            "schedule": crontab(minute="*/15"),
        },
        # Anti no-show: expirar citas sin confirmar y disparar waitlist
        "expire-unconfirmed-appointments": {
            "task": "app.tasks.appointment_confirmations.expire_unconfirmed",
            "schedule": crontab(minute="*/5"),
        },
        # Waitlist: expirar ofertas no respondidas y pasar al siguiente
        "expire-waitlist-offers": {
            "task": "app.tasks.waitlist_matching.expire_offers_task",
            "schedule": crontab(minute="*/10"),
        },
    },

    # Resultados expiran en 24h
    result_expires=86400,
)
