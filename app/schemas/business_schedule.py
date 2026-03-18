from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Any

from app.models.business_schedule import ScheduleMode


class BusinessScheduleCreate(BaseModel):
    """
    Crea o reemplaza el horario del negocio.

    schedule_data para mode=time_slots:
        {"monday": ["09:00", "10:00", "11:00"], "tuesday": [...], ...}

    schedule_data para mode=capacity:
        {"monday": {"morning": 3, "afternoon": 2}, "tuesday": {...}, ...}

    Los días sin disponibilidad simplemente se omiten del dict.
    """
    mode: ScheduleMode = ScheduleMode.TIME_SLOTS
    schedule_data: dict[str, Any]
    slot_duration_minutes: int = 60
    max_days_ahead: int = 14
    is_active: bool = True

    @field_validator("max_days_ahead")
    @classmethod
    def validate_max_days(cls, v: int) -> int:
        if not (1 <= v <= 60):
            raise ValueError("max_days_ahead debe estar entre 1 y 60")
        return v

    @field_validator("slot_duration_minutes")
    @classmethod
    def validate_slot_duration(cls, v: int) -> int:
        if not (15 <= v <= 480):
            raise ValueError("slot_duration_minutes debe estar entre 15 y 480")
        return v


class BusinessScheduleUpdate(BaseModel):
    mode: ScheduleMode | None = None
    schedule_data: dict[str, Any] | None = None
    slot_duration_minutes: int | None = None
    max_days_ahead: int | None = None
    is_active: bool | None = None


class BusinessScheduleResponse(BaseModel):
    id: UUID
    business_id: UUID
    mode: ScheduleMode
    schedule_data: dict[str, Any]
    slot_duration_minutes: int
    max_days_ahead: int
    is_active: bool

    model_config = {"from_attributes": True}
