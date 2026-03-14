from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.core.deps import get_current_business
from app.models.business import Business, PlanType
from app.schemas.business import BusinessCreate, BusinessUpdate, BusinessResponse

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.post("/", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_business(data: BusinessCreate, db: AsyncSession = Depends(get_db)):
    # Normalizar plan al valor de enum (minúsculas en DB)
    if isinstance(data.plan, PlanType):
        plan_enum = data.plan
    elif data.plan:
        plan_enum = PlanType(str(data.plan).lower()) if str(data.plan).lower() in {p.value for p in PlanType} else PlanType.FREE
    else:
        plan_enum = PlanType.FREE

    business = Business(
        name=data.name,
        business_type=data.business_type,
        whatsapp_phone=data.whatsapp_phone,
        email=data.email,
        plan=plan_enum,
    )
    db.add(business)
    await db.flush()
    await db.refresh(business)
    return business


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(business_id: UUID, current: Business = Depends(get_current_business), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    return business


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(business_id: UUID, data: BusinessUpdate, current: Business = Depends(get_current_business), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(business, field, value)

    await db.flush()
    await db.refresh(business)
    return business
