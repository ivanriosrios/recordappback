"""
Task Celery: enviar un recordatorio por WhatsApp y registrar el log.
"""
import logging
from datetime import datetime, timedelta, date

from app.tasks.celery_app import celery_app
from app.tasks.db_utils import get_sync_session
from app.services.whatsapp import whatsapp

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.send_reminder.send_reminder_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutos entre reintentos
)
def send_reminder_task(self, reminder_id: str):
    """
    Envía un recordatorio por WhatsApp y registra el resultado.

    Flujo:
    1. Carga reminder + relaciones
    2. Verifica que siga activo (no fue cancelado mientras esperaba en cola)
    3. Renderiza el mensaje con las variables del cliente/servicio
    4. Llama a WhatsApp Cloud API
    5. Registra ReminderLog (sent / failed)
    6. Si recurrente: actualiza next_send_date
    7. Si one_time: marca status=done
    """
    session = get_sync_session()

    try:
        from app.models.reminder import Reminder, ReminderStatus, ReminderType
        from app.models.reminder_log import ReminderLog, LogStatus, LogChannel
        from app.models.client import Client
        from app.models.service import Service
        from app.models.template import Template
        from app.models.business import Business

        # Cargar reminder
        reminder = session.get(Reminder, reminder_id)
        if not reminder:
            logger.warning(f"[send_reminder] Reminder {reminder_id} no encontrado")
            return

        if reminder.status != ReminderStatus.ACTIVE:
            logger.info(f"[send_reminder] Reminder {reminder_id} ya no está activo, skip")
            return

        # Cargar relaciones
        client = session.get(Client, str(reminder.client_id))
        service = session.get(Service, str(reminder.service_id))
        template = session.get(Template, str(reminder.template_id))

        # Cargar business para nombre
        business = session.get(Business, str(client.business_id))

        if not all([client, service, template, business]):
            logger.error(f"[send_reminder] Datos incompletos para reminder {reminder_id}")
            return

        # Verificar opt-out
        from app.models.client import ClientStatus
        if client.status == ClientStatus.OPTOUT:
            logger.info(f"[send_reminder] Cliente {client.id} en opt-out, skip")
            reminder.status = ReminderStatus.DONE
            session.commit()
            return

        # Enviar por WhatsApp usando template aprobado por Meta
        try:
            meta_name = template.meta_template_name or "recordatorio_cita"
            meta_lang = template.meta_language_code or "es_CO"

            # Componentes según la plantilla Meta publicada
            if meta_name == "encuesta_servicio":
                # Hola {{1}}, hace poco te atendimos en {{2}} con el servicio {{3}}...
                body_params = [client.display_name, business.name, service.name]
            elif meta_name == "reactivacion_cliente":
                # Hola {{1}}, hace tiempos que no te vemos {{2}}...
                body_params = [client.display_name, business.name]
            else:
                # Por defecto: cliente, servicio, negocio
                body_params = [client.display_name, service.name, business.name]

            components = whatsapp.build_body_components(*body_params)
            result = whatsapp.send_template(
                to=client.phone,
                template_name=meta_name,
                language_code=meta_lang,
                components=components,
            )
        except ValueError as exc:
            # Número inválido (sin indicativo, caracteres no numéricos, etc.)
            log = ReminderLog(
                reminder_id=reminder.id,
                sent_at=datetime.utcnow(),
                channel=LogChannel.WHATSAPP,
                status=LogStatus.FAILED,
                client_response=str(exc),
            )
            session.add(log)
            reminder.status = ReminderStatus.DONE  # No reintentar hasta corregir el número
            session.commit()
            logger.error(f"[send_reminder] Número inválido: {exc}")
            return

        # Registrar log
        log_status = LogStatus.SENT if result["success"] else LogStatus.FAILED
        log = ReminderLog(
            reminder_id=reminder.id,
            sent_at=datetime.utcnow(),
            channel=LogChannel.WHATSAPP,
            status=log_status,
            wa_message_id=result.get("wa_message_id"),
        )
        session.add(log)

        # === Crear notificación in-app ===
        from app.services.notifications import create_notification_sync
        from app.models.notification import NotificationType

        if result["success"]:
            create_notification_sync(
                session,
                business.id,
                NotificationType.REMINDER_SENT,
                f"Recordatorio enviado a {client.display_name}",
                f"Mensaje enviado exitosamente a {client.phone}",
            )
            reminder.last_sent_at = datetime.utcnow()

            if reminder.type == ReminderType.RECURRING and reminder.recurrence_days:
                # Calcular próxima fecha
                reminder.next_send_date = date.today() + timedelta(
                    days=reminder.recurrence_days
                )
                logger.info(f"[send_reminder] Próximo envío: {reminder.next_send_date}")
            else:
                reminder.status = ReminderStatus.DONE
                logger.info(f"[send_reminder] Reminder {reminder_id} completado")
        else:
            error_msg = result.get("error", "Error WhatsApp")
            create_notification_sync(
                session,
                business.id,
                NotificationType.REMINDER_FAILED,
                f"Fallo al enviar recordatorio a {client.display_name}",
                f"Error: {error_msg}",
            )
            # Evitar reintentos si el destinatario no está en la allowlist de WhatsApp Cloud
            allowlist_marker = "recipient phone number not in allowed list"
            code_marker = "131030"
            template_missing_marker = "template name does not exist"
            template_code_marker = "132001"
            params_mismatch_marker = "number of parameters does not match"
            params_code_marker = "132000"
            if (
                allowlist_marker in error_msg.lower()
                or code_marker in error_msg
                or template_missing_marker in error_msg.lower()
                or template_code_marker in error_msg
                or params_mismatch_marker in error_msg.lower()
                or params_code_marker in error_msg
            ):
                reminder.status = ReminderStatus.DONE
                if template_missing_marker in error_msg.lower() or template_code_marker in error_msg:
                    logger.error(
                        "[send_reminder] Template no existe/aprobado; marcar DONE y no reintentar"
                    )
                elif params_mismatch_marker in error_msg.lower() or params_code_marker in error_msg:
                    logger.error(
                        "[send_reminder] Template tiene distinto número de parámetros; marcar DONE y revisar variables/components"
                    )
                else:
                    logger.error(
                        "[send_reminder] Destinatario no está en allowlist de WhatsApp; marcar DONE"
                    )
            else:
                logger.error(f"[send_reminder] Fallo al enviar: {error_msg}")
                # Reintento automático
                raise self.retry(exc=Exception(error_msg))

        session.commit()
        logger.info(f"[send_reminder] OK — reminder={reminder_id} status={log_status}")

    except Exception as exc:
        session.rollback()
        logger.exception(f"[send_reminder] Excepción en reminder {reminder_id}: {exc}")
        raise
    finally:
        session.close()
