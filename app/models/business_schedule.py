import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ScheduleMode(str, enum.Enum):
    TIME_SLOTS = "time_slots"
    CAPACITY = "capacity"


class BusinessSchedule(Base):
    __tablename__ = "business_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, unique=True
    )
    mode: Mapped[ScheduleMode] = mapped_column(
        SAEnum(ScheduleMode, name="schedulemode", create_type=False),
        nullable=False,
        default=ScheduleMode.TIME_SLOTS,
    )
    schedule_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_days_ahead: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    business: Mapped["Business"] = relationship("Business")

    def __repr__(self) -> str:
        return f"<BusinessSchedule business={self.business_id} mode={self.mode}>"
