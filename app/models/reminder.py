import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

import enum


class ReminderType(str, enum.Enum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class ReminderStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    type: Mapped[ReminderType] = mapped_column(
        SAEnum(ReminderType, name="remindertype", values_callable=lambda enum_cls: [e.value for e in enum_cls], create_type=False),
        default=ReminderType.ONE_TIME,
        nullable=False,
    )
    recurrence_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_send_date: Mapped[date] = mapped_column(Date, nullable=False)
    notify_days_before: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(
        SAEnum(ReminderStatus, name="reminderstatus", values_callable=lambda enum_cls: [e.value for e in enum_cls], create_type=False),
        default=ReminderStatus.ACTIVE,
        nullable=False,
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="reminders")
    service: Mapped["Service"] = relationship("Service", back_populates="reminders")
    template: Mapped["Template"] = relationship("Template", back_populates="reminders")
    logs: Mapped[list["ReminderLog"]] = relationship("ReminderLog", back_populates="reminder", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Reminder {self.id} -> {self.client_id}>"
