"""
Seedea las 5 plantillas de sistema (Meta-aprobadas) para un business.
Se llama al registrar un negocio nuevo o bajo demanda desde un endpoint admin.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import (
    Template,
    TemplateType,
    TemplateChannel,
    TemplateStatus,
)

logger = logging.getLogger(__name__)

# Definición de las plantillas del sistema.
# name = nombre amigable para el usuario
# body = preview del mensaje (lo que ve el cliente en la app)
# meta_template_name = nombre exacto en Meta
# meta_language_code = idioma exacto en Meta (es_CO para Spanish Colombia)
# status = estado en Meta (approved = usable, pending = en revisión)
SYSTEM_TEMPLATES = [
    {
        "name": "Mensaje de prueba",
        "body": "Hello World! Este es un mensaje de prueba de RecordApp.",
        "type": TemplateType.REMINDER,
        "meta_template_name": "hello_world",
        "meta_language_code": "en_US",
        "status": TemplateStatus.APPROVED,
    },
    {
        "name": "Recordatorio de cita",
        "body": "Hola {nombre_cliente}, te recordamos tu cita de {servicio} en {negocio}. Te esperamos!",
        "type": TemplateType.REMINDER,
        "meta_template_name": "recordatorio_cita",
        "meta_language_code": "es_CO",
        "status": TemplateStatus.PENDING,  # En revisión en Meta
    },
    {
        "name": "Feliz cumpleaños",
        "body": "Feliz cumpleaños {nombre_cliente}! De parte de {negocio} te deseamos un excelente día.",
        "type": TemplateType.BIRTHDAY,
        "meta_template_name": "feliz_cumpleanos",
        "meta_language_code": "es_CO",
        "status": TemplateStatus.PENDING,  # En revisión en Meta
    },
    {
        "name": "Encuesta post-servicio",
        "body": "Hola {nombre_cliente}, hace poco te atendimos en {negocio} con el servicio {servicio}. ¿Cómo te fue? Responde: 1-Excelente 2-Bien 3-Regular 4-Mal",
        "type": TemplateType.FOLLOW_UP,
        "meta_template_name": "encuesta_servicio",
        "meta_language_code": "es_CO",
        "status": TemplateStatus.APPROVED,  # Activa en Meta
    },
    {
        "name": "Reactivación de cliente",
        "body": "Hola {nombre_cliente}, hace tiempos que no te vemos {negocio}. Queremos mejorar la calidad del servicio si nos envias una retroalimentación, no queremos perder clientes valiosos como tú.",
        "type": TemplateType.REACTIVATION,
        "meta_template_name": "reactivacion_cliente",
        "meta_language_code": "es_CO",
        "status": TemplateStatus.APPROVED,  # Activa en Meta
    },
    {
        "name": "Confirmación de opt-out",
        "body": "Has sido dado de baja de los mensajes de {negocio}. Si deseas reactivar, escribe ACTIVAR.",
        "type": TemplateType.PROMO,
        "meta_template_name": "confirmacion_optout",
        "meta_language_code": "es_CO",
        "status": TemplateStatus.PENDING,  # No creada aún en Meta
    },
]


async def seed_system_templates(db: AsyncSession, business_id: UUID) -> list[Template]:
    """
    Crea las plantillas del sistema para un business si no existen.
    Si ya existen, actualiza el language_code y status por si cambiaron.
    Retorna la lista de templates creados o existentes.
    """
    created = []

    for tpl_def in SYSTEM_TEMPLATES:
        # Verificar si ya existe por meta_template_name + business_id
        result = await db.execute(
            select(Template).where(
                Template.business_id == business_id,
                Template.meta_template_name == tpl_def["meta_template_name"],
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Actualizar language_code y status si cambiaron
            changed = False
            if existing.meta_language_code != tpl_def["meta_language_code"]:
                existing.meta_language_code = tpl_def["meta_language_code"]
                changed = True
            if existing.status != tpl_def["status"]:
                existing.status = tpl_def["status"]
                changed = True
            if existing.body != tpl_def["body"]:
                existing.body = tpl_def["body"]
                changed = True
            if changed:
                logger.info(f"[seeder] Template '{tpl_def['name']}' actualizado para business {business_id}")
            created.append(existing)
            continue

        template = Template(
            business_id=business_id,
            name=tpl_def["name"],
            body=tpl_def["body"],
            type=tpl_def["type"],
            channel=TemplateChannel.WHATSAPP,
            meta_template_name=tpl_def["meta_template_name"],
            meta_language_code=tpl_def["meta_language_code"],
            status=tpl_def["status"],
            is_system=True,
        )
        db.add(template)
        created.append(template)
        logger.info(f"[seeder] Template '{tpl_def['name']}' creado para business {business_id}")

    await db.flush()
    return created
