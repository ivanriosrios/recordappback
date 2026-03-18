from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import Any

from app.models.appointment import AppointmentStatus, AppointmentShift


class AppointmentResponse(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    service_id: UUID | None
    status: AppointmentStatus
    appointment_date: date
    # Stored as "HH:MM" string in the DB — keep as str to avoid coercion issues
    appointment_time: str | None = None
    shift: AppointmentShift | None = None
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    reminder_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentUpdate(BaseModel):
    """Payload para acciones de gestión desde el negocio."""
    status: AppointmentStatus | None = None
    appointment_time: str | None = None  # "HH:MM"
    shift: AppointmentShift | None = None


class AppointmentListItem(BaseModel):
    """Vista resumida para listados."""
    id: UUID
    client_id: UUID
    client_name: str | None = None
    service_id: UUID | None = None
    service_name: str | None = None
    status: AppointmentStatus
    appointment_date: date
    # Stored as "HH:MM" string in the DB — keep as str to avoid coercion issues
    appointment_time: str | None = None
    shift: AppointmentShift | None = None
    confirmed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
