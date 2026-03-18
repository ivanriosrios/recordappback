"""
Endpoints para configuración de horarios del negocio (KOS-51).

GET    /businesses/{id}/schedule   — obtener horario
PUT    /businesses/{id}/schedule   — crear o reemplazar
PATCH  /businesses/{id}/schedule   — actualizar parcialmente
DELETE /businesses/{id}/schedule   — eliminar
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.business_schedule import BusinessSchedule, ScheduleMode

router = APIRouter(prefix="/businesses/{business_id}/schedule", tags=["schedule"])


class ScheduleUpsert(BaseModel):
    mode: Optional[str] = "time_slots"
    schedule_data: Optional[dict] = Field(default_factory=dict)
    slot_duration_minutes: Optional[int] = Field(30, ge=15, le=480)
    max_days_ahead: Optional[int] = Field(30, ge=1, le=60)
    is_active: Optional[bool] = True


def _schedule_dict(s: BusinessSchedule) -> dict:
    return {
        "id": str(s.id),
        "business_id": str(s.business_id),
        "mode": s.mode,
        "schedule_data": s.schedule_data,
        "slot_duration_minutes": s.slot_duration_minutes,
        "max_days_ahead": s.max_days_ahead,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


@router.get("")
@router.get("/")
async def get_schedule(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BusinessSchedule).where(BusinessSchedule.business_id == business_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Horario no configurado")
    return _schedule_dict(sched)


@router.put("")
@router.put("/")
async def upsert_schedule(
    business_id: UUID,
    data: ScheduleUpsert,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BusinessSchedule).where(BusinessSchedule.business_id == business_id)
    )
    sched = result.scalar_one_or_none()

    try:
        mode = ScheduleMode(data.mode or "time_slots")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Modo inválido: {data.mode}")

    if sched:
        sched.mode = mode
        sched.schedule_data = data.schedule_data or {}
        sched.slot_duration_minutes = data.slot_duration_minutes or 30
        sched.max_days_ahead = data.max_days_ahead or 30
        sched.is_active = data.is_active if data.is_active is not None else True
    else:
        sched = BusinessSchedule(
            business_id=business_id,
            mode=mode,
            schedule_data=data.schedule_data or {},
            slot_duration_minutes=data.slot_duration_minutes or 30,
            max_days_ahead=data.max_days_ahead or 30,
            is_active=data.is_active if data.is_active is not None else True,
        )
        db.add(sched)

    await db.flush()
    await db.refresh(sched)
    return _schedule_dict(sched)


@router.patch("")
@router.patch("/")
async def patch_schedule(
    business_id: UUID,
    data: dict,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BusinessSchedule).where(BusinessSchedule.business_id == business_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Horario no configurado")

    allowed = {"mode", "schedule_data", "slot_duration_minutes", "max_days_ahead", "is_active"}
    for key, val in data.items():
        if key in allowed and val is not None:
            if key == "mode":
                try:
                    val = ScheduleMode(val)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Modo inválido: {val}")
            setattr(sched, key, val)

    await db.flush()
    await db.refresh(sched)
    return _schedule_dict(sched)


@router.delete("")
@router.delete("/")
async def delete_schedule(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BusinessSchedule).where(BusinessSchedule.business_id == business_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Horario no configurado")
    await db.delete(sched)
    return {"detail": "Horario eliminado"}
