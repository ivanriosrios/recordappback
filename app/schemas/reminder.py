from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import date, datetime
from app.models.reminder import ReminderType, ReminderStatus


class ReminderCreate(BaseModel):
    client_id: UUID
    service_id: UUID
    template_id: UUID
    type: ReminderType = ReminderType.ONE_TIME
    recurrence_days: int | None = None
    next_send_date: date
    notify_days_before: int = 3

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if v is None:
            return ReminderType.ONE_TIME
        val = str(v).lower()
        return ReminderType(val) if val in {t.value for t in ReminderType} else ReminderType.ONE_TIME


class ReminderUpdate(BaseModel):
    template_id: UUID | None = None
    type: ReminderType | None = None
    recurrence_days: int | None = None
    next_send_date: date | None = None
    notify_days_before: int | None = None
    status: ReminderStatus | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return ReminderType(val) if val in {t.value for t in ReminderType} else ReminderType.ONE_TIME

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return ReminderStatus(val) if val in {s.value for s in ReminderStatus} else ReminderStatus.ACTIVE


class ReminderResponse(BaseModel):
    id: UUID
    client_id: UUID
    service_id: UUID
    template_id: UUID
    type: ReminderType
    recurrence_days: int | None
    next_send_date: date
    notify_days_before: int
    status: ReminderStatus
    last_sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
