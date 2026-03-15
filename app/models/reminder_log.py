import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

import enum


class LogChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"


class LogStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    RESPONDED_YES = "responded_yes"
    RESPONDED_NO = "responded_no"
    FAILED = "failed"
    RATED_GOOD = "rated_good"  # respondió BIEN a la encuesta post-servicio
    RATED_BAD = "rated_bad"    # respondió MAL a la encuesta post-servicio


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reminder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reminders.id"), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    channel: Mapped[LogChannel] = mapped_column(
        SAEnum(LogChannel, values_callable=lambda e: [x.value for x in e]),
        default=LogChannel.WHATSAPP,
        nullable=False,
    )
    status: Mapped[LogStatus] = mapped_column(
        SAEnum(LogStatus, values_callable=lambda e: [x.value for x in e]),
        default=LogStatus.SENT,
        nullable=False,
    )
    client_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    wa_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    reminder: Mapped["Reminder"] = relationship("Reminder", back_populates="logs")

    def __repr__(self) -> str:
        return f"<ReminderLog {self.id} status={self.status}>"
