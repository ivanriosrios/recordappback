"""
Helper para crear notificaciones en tareas Celery y funciones síncronas.
"""
from uuid import UUID
from app.models.notification import Notification, NotificationType


def create_notification_sync(
    session,
    business_id: UUID,
    type: NotificationType,
    title: str,
    body: str = None,
):
    """
    Crea una notificación para usar desde Celery tasks (sesión sync).

    Args:
        session: SQLAlchemy sync session
        business_id: UUID del negocio
        type: NotificationType enum
        title: Título de la notificación
        body: Body (opcional)

    Returns:
        Notification instance (ya agregada a la sesión)
    """
    notif = Notification(
        business_id=business_id, type=type, title=title, body=body
    )
    session.add(notif)
    return notif
