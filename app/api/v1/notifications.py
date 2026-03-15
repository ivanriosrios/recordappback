"""
Endpoints para notificaciones in-app del negocio.

GET    /businesses/{business_id}/notifications — lista notificaciones
PATCH  /businesses/{business_id}/notifications/{notification_id}/read — marca como leída
POST   /businesses/{business_id}/notifications/read_all — marca todas como leídas
GET    /businesses/{business_id}/notifications/unread_count — cuenta no leídas
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from uuid import UUID

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.notification import Notification

router = APIRouter(
    prefix="/businesses/{business_id}/notifications",
    tags=["notifications"],
)


@router.get("/")
async def list_notifications(
    business_id: UUID,
    skip: int = 0,
    limit: int = 50,
    read: bool | None = None,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista notificaciones del negocio (paginadas, más nuevas primero).

    Query params:
    - read: filtrar por estado (true=leídas, false=no leídas)
    - skip, limit: para paginación
    """
    query = select(Notification).where(Notification.business_id == business_id)

    if read is not None:
        query = query.where(Notification.read == read)

    query = query.order_by(desc(Notification.created_at))

    result = await db.execute(query.offset(skip).limit(limit))
    notifications = result.scalars().all()

    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "read": n.read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@router.get("/unread_count")
async def get_unread_count(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Retorna cantidad de notificaciones no leídas."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(Notification.business_id == business_id, Notification.read == False)
        )
    )
    count = result.scalar() or 0
    return {"count": count}


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    business_id: UUID,
    notification_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Marca una notificación como leída."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.business_id == business_id,
            )
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )

    notification.read = True
    await db.commit()

    return {
        "id": str(notification.id),
        "read": notification.read,
    }


@router.post("/read_all")
async def mark_all_notifications_as_read(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Marca todas las notificaciones como leídas."""
    result = await db.execute(
        select(Notification).where(
            and_(Notification.business_id == business_id, Notification.read == False)
        )
    )
    notifications = result.scalars().all()

    for n in notifications:
        n.read = True

    await db.commit()

    return {"marked_as_read": len(notifications)}
