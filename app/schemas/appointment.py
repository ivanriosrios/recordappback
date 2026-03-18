from pydantic import BaseModel
from uuid import UUID
from datetime import date, time, datetime
from typing import Any

from app.models.appointment import AppointmentStatus, AppointmentShift


class AppointmentResponse(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    service_id: UUID | None
    status: AppointmentStatus
    appointment_date: date
    appointment_time: time | None
    shift: AppointmentShift | None
    confirmed_at: datetime | None
    completed_at: datetime | None
    reminder_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentUpdate(BaseModel):
    """Payload para acciones de gestión desde el negocio."""
    status: AppointmentStatus | None = None
    appointment_time: time | None = None
    shift: AppointmentShift | None = None


class AppointmentListItem(BaseModel):
    """Vista resumida para listados."""
    id: UUID
    client_id: UUID
    client_name: str | None = None
    service_id: UUID | None
    service_name: str | None = None
    status: AppointmentStatus
    appointment_date: date
    appointment_time: time | None
    shift: AppointmentShift | None
    confirmed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
