"""
API de Horario del Negocio (BusinessSchedule) — KOS-51.

Permite configurar los días y horas disponibles para agendar citas,
el modo de horario (slots exactos vs turnos), y la ventana de días
hacia adelante que el chatbot mostrará a los clientes.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.business_schedule import BusinessSchedule
from app.schemas.business_schedule import (
    BusinessScheduleCreate,
    BusinessScheduleResponse,
    BusinessScheduleUpdate,
)

router = APIRouter(prefix="/businesses/{business_id}/schedule", tags=["schedule"])


async def _get_schedule(db: AsyncSession, business_id: UUID) -> BusinessSchedule | None:
    result = await db.execute(
        select(BusinessSchedule).where(BusinessSchedule.business_id == business_id)
    )
    return result.scalar_one_or_none()


@router.get("/", response_model=BusinessScheduleResponse)
async def get_schedule(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el horario configurado del negocio."""
    schedule = await _get_schedule(db, business_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="El negocio no tiene horario configurado")
    return schedule


@router.put("/", response_model=BusinessScheduleResponse, status_code=status.HTTP_200_OK)
async def upsert_schedule(
    business_id: UUID,
    data: BusinessScheduleCreate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea o reemplaza el horario del negocio.

    Si ya existe un horario, lo actualiza completamente.
    Si no existe, lo crea.

    Ejemplo de schedule_data para mode=time_slots:
    ```json
    {
      "monday":    ["09:00", "10:00", "11:00", "14:00", "15:00"],
      "tuesday":   ["09:00", "10:00", "11:00"],
      "wednesday": ["09:00", "10:00", "11:00", "14:00", "15:00"],
      "thursday":  ["09:00", "10:00", "11:00"],
      "friday":    ["09:00", "10:00", "11:00", "14:00", "15:00"],
      "saturday":  ["09:00", "10:00"]
    }
    ```

    Ejemplo para mode=capacity:
    ```json
    {
      "monday":   {"morning": 5, "afternoon": 3},
      "tuesday":  {"morning": 5, "afternoon": 3},
      "saturday": {"morning": 4}
    }
    ```
    """
    schedule = await _get_schedule(db, business_id)

    if schedule:
        # Actualizar existente
        schedule.mode = data.mode
        schedule.schedule_data = data.schedule_data
        schedule.slot_duration_minutes = data.slot_duration_minutes
        schedule.max_days_ahead = data.max_days_ahead
        schedule.is_active = data.is_active
    else:
        # Crear nuevo
        schedule = BusinessSchedule(
            business_id=business_id,
            mode=data.mode,
            schedule_data=data.schedule_data,
            slot_duration_minutes=data.slot_duration_minutes,
            max_days_ahead=data.max_days_ahead,
            is_active=data.is_active,
        )
        db.add(schedule)

    await db.flush()
    await db.refresh(schedule)
    return schedule


@router.patch("/", response_model=BusinessScheduleResponse)
async def patch_schedule(
    business_id: UUID,
    data: BusinessScheduleUpdate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza parcialmente el horario del negocio."""
    schedule = await _get_schedule(db, business_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="El negocio no tiene horario configurado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.flush()
    await db.refresh(schedule)
    return schedule


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    business_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Elimina el horario del negocio (deshabilita el chatbot de agendamiento)."""
    schedule = await _get_schedule(db, business_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="El negocio no tiene horario configurado")

    await db.delete(schedule)
