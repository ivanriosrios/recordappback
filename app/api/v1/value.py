"""
Dashboard 'Valor RecordApp' — métricas que sustentan el ROI percibido.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.services.value_dashboard import compute

router = APIRouter(prefix="/businesses/{business_id}/value", tags=["value"])


@router.get("/")
async def value_dashboard(
    business_id: UUID,
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    attribution_days: int = Query(7, ge=1, le=30),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await compute(db, business_id, period=period, attribution_days=attribution_days)
    return result.to_dict()
