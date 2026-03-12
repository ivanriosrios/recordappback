from pydantic import BaseModel
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


class ReminderUpdate(BaseModel):
    template_id: UUID | None = None
    type: ReminderType | None = None
    recurrence_days: int | None = None
    next_send_date: date | None = None
    notify_days_before: int | None = None
    status: ReminderStatus | None = None


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
