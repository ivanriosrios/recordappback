from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import timedelta
from typing import Optional

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.service_log import ServiceLog
from app.models.service import Service
from app.models.client import Client
from app.schemas.service_log import ServiceLogCreate, ServiceLogComplete, ServiceLogResponse
from app.tasks.send_follow_up import send_follow_up_task

router = APIRouter(prefix="/businesses/{business_id}/service-logs", tags=["service-logs"])


@router.post("/", response_model=ServiceLogResponse, status_code=status.HTTP_201_CREATED)
async def create_service_log(business_id: UUID, data: ServiceLogCreate, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    # Validar cliente y servicio pertenecen al negocio
    svc_result = await db.execute(select(Service).where(Service.id == data.service_id, Service.business_id == business_id))
    service = svc_result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado para este negocio")

    cli_result = await db.execute(select(Client).where(Client.id == data.client_id, Client.business_id == business_id))
    client = cli_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado para este negocio")

    log = ServiceLog(
        business_id=business_id,
        client_id=data.client_id,
        service_id=data.service_id,
        notes=data.notes,
        follow_up_sent=False,
        rating=None,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    # Programar follow-up si el servicio tiene follow_up_days
    if service.follow_up_days:
        countdown = max(service.follow_up_days * 24 * 60 * 60, 0)
        send_follow_up_task.apply_async(
            args=[str(log.id)],
            countdown=countdown,
        )

    # Enriquecer respuesta con nombres
    response = ServiceLogResponse(
        **log.__dict__,
        client_name=client.display_name,
        service_name=service.name,
    )
    return response


@router.get("/", response_model=list[ServiceLogResponse])
async def list_service_logs(
    business_id: UUID,
    rating: Optional[int] = Query(None, description="Filtrar por calificación (1-5). Usa 0 para logs sin calificación."),
    follow_up_pending: Optional[bool] = Query(None, description="True = follow-up enviado pero sin calificación"),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    query = select(ServiceLog).where(ServiceLog.business_id == business_id)

    if rating is not None:
        if rating == 0:
            query = query.where(ServiceLog.rating.is_(None))
        else:
            query = query.where(ServiceLog.rating == rating)

    if follow_up_pending is True:
        query = query.where(
            ServiceLog.follow_up_sent.is_(True),
            ServiceLog.rating.is_(None),
        )

    query = query.order_by(ServiceLog.completed_at.desc())
    result = await db.execute(query)
    logs = result.scalars().all()

    # Prefetch nombres mínimos
    client_ids = {log.client_id for log in logs}
    service_ids = {log.service_id for log in logs}

    clients = {}
    if client_ids:
        cresult = await db.execute(select(Client).where(Client.id.in_(client_ids)))
        clients = {c.id: c.display_name for c in cresult.scalars().all()}

    services = {}
    follow_up_days_map = {}
    if service_ids:
        sresult = await db.execute(select(Service).where(Service.id.in_(service_ids)))
        for s in sresult.scalars().all():
            services[s.id] = s.name
            follow_up_days_map[s.id] = s.follow_up_days

    return [
        ServiceLogResponse(
            **log.__dict__,
            client_name=clients.get(log.client_id),
            service_name=services.get(log.service_id),
            follow_up_days=follow_up_days_map.get(log.service_id),
        )
        for log in logs
    ]


@router.post("/{log_id}/complete", response_model=ServiceLogResponse)
async def complete_service_log(
    business_id: UUID,
    log_id: UUID,
    data: ServiceLogComplete,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Cierra un servicio: registra precio cobrado, método de pago y notas.
    Si send_summary=True, envía un resumen/comprobante por WhatsApp al cliente.
    """
    result = await db.execute(
        select(ServiceLog).where(
            ServiceLog.id == log_id,
            ServiceLog.business_id == business_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Registro de servicio no encontrado")

    # Actualizar campos
    if data.price_charged is not None:
        log.price_charged = data.price_charged
    if data.payment_method is not None:
        log.payment_method = data.payment_method
    if data.service_notes is not None:
        log.service_notes = data.service_notes
    if data.notes is not None:
        log.notes = data.notes

    await db.flush()
    await db.refresh(log)

    # Enriquecer respuesta
    cli_result = await db.execute(select(Client).where(Client.id == log.client_id))
    client = cli_result.scalar_one_or_none()
    svc_result = await db.execute(select(Service).where(Service.id == log.service_id))
    service = svc_result.scalar_one_or_none()

    # Enviar resumen por WhatsApp si se solicitó y aún no se envió
    if data.send_summary and not log.summary_sent:
        from app.tasks.send_service_summary import send_service_summary_task
        send_service_summary_task.delay(str(log.id))

    return ServiceLogResponse(
        **log.__dict__,
        client_name=client.display_name if client else None,
        service_name=service.name if service else None,
    )


@router.post("/{log_id}/send_followup", status_code=status.HTTP_202_ACCEPTED)
async def send_follow_up_now(
    business_id: UUID,
    log_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Envía la encuesta post-servicio inmediatamente para un ServiceLog pendiente."""
    result = await db.execute(
        select(ServiceLog).where(
            ServiceLog.id == log_id,
            ServiceLog.business_id == business_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Registro de servicio no encontrado")
    if log.follow_up_sent:
        raise HTTPException(status_code=400, detail="La encuesta ya fue enviada")

    send_follow_up_task.delay(str(log.id))
    return {"message": "Encuesta encolada para envío inmediato", "log_id": str(log.id)}


@router.post("/{log_id}/skip_followup", status_code=status.HTTP_200_OK)
async def skip_follow_up(
    business_id: UUID,
    log_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Cancela/omite la encuesta post-servicio para un ServiceLog (marca como enviado sin enviar)."""
    result = await db.execute(
        select(ServiceLog).where(
            ServiceLog.id == log_id,
            ServiceLog.business_id == business_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Registro de servicio no encontrado")
    if log.follow_up_sent:
        raise HTTPException(status_code=400, detail="La encuesta ya fue procesada")

    log.follow_up_sent = True
    await db.commit()
    return {"message": "Encuesta cancelada", "log_id": str(log.id)}
