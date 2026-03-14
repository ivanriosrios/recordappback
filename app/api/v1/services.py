from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse

router = APIRouter(prefix="/businesses/{business_id}/services", tags=["services"])


@router.post("/", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(business_id: UUID, data: ServiceCreate, db: AsyncSession = Depends(get_db)):
    service = Service(
        business_id=business_id,
        name=data.name,
        description=data.description,
        ref_price=data.ref_price,
        follow_up_days=data.follow_up_days,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


@router.get("/", response_model=list[ServiceResponse])
async def list_services(business_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Service).where(Service.business_id == business_id, Service.is_active == True)
    )
    return result.scalars().all()


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(business_id: UUID, service_id: UUID, data: ServiceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Service).where(Service.id == service_id, Service.business_id == business_id)
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    await db.flush()
    await db.refresh(service)
    return service
