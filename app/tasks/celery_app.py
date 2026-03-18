"""
Configuración de Celery con Redis como broker y backend.
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "recordapp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.send_reminder",
        "app.tasks.send_follow_up",
        "app.tasks.send_birthday",
        "app.tasks.send_reactivation",
        "app.tasks.send_service_summary",
        "app.tasks.send_appointment_reminder",
        "app.tasks.notify_pending_appointments",
        "app.tasks.scheduler",
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
        # Cada hora (:30) revisa citas confirmadas mañana y envía recordatorio
        "check-appointment-reminders": {
            "task": "app.tasks.scheduler.check_appointment_reminders",
            "schedule": crontab(minute=30),
        },
        # Cada 2h alerta al negocio sobre citas sin confirmar
        "check-pending-appointments": {
            "task": "app.tasks.notify_pending_appointments.notify_pending_appointments_task",
            "schedule": crontab(minute=0, hour="*/2"),
        },
    },

    # Resultados expiran en 24h
    result_expires=86400,
)
