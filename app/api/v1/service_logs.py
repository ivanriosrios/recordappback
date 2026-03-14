from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import timedelta

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.service_log import ServiceLog
from app.models.service import Service
from app.models.client import Client
from app.schemas.service_log import ServiceLogCreate, ServiceLogResponse
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
async def list_service_logs(business_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceLog).where(ServiceLog.business_id == business_id).order_by(ServiceLog.completed_at.desc())
    )
    logs = result.scalars().all()

    # Prefetch nombres mínimos
    client_ids = {log.client_id for log in logs}
    service_ids = {log.service_id for log in logs}

    clients = {}
    if client_ids:
        cresult = await db.execute(select(Client).where(Client.id.in_(client_ids)))
        clients = {c.id: c.display_name for c in cresult.scalars().all()}

    services = {}
    if service_ids:
        sresult = await db.execute(select(Service).where(Service.id.in_(service_ids)))
        services = {s.id: s.name for s in sresult.scalars().all()}

    return [
        ServiceLogResponse(
            **log.__dict__,
            client_name=clients.get(log.client_id),
            service_name=services.get(log.service_id),
        )
        for log in logs
    ]
