import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    REMINDER_SENT = "reminder_sent"
    REMINDER_FAILED = "reminder_failed"
    CLIENT_RESPONDED = "client_responded"
    CLIENT_OPTOUT = "client_optout"
    FOLLOW_UP_RATED = "follow_up_rated"
    BIRTHDAY_SENT = "birthday_sent"
    REACTIVATION_SENT = "reactivation_sent"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(SAEnum(NotificationType, name="notificationtype"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Notification {self.id} type={self.type} read={self.read}>"
