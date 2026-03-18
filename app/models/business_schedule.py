"""
Modelo BusinessSchedule — configuración de horarios y capacidad del negocio.

Dos modos de agendamiento:
- time_slots: turnos fijos (barbería, clínica dental).
  schedule_data = {"monday": ["09:00","10:00","11:00"], ...}
- capacity: capacidad por turno (mecánica, car wash).
  schedule_data = {"monday": {"morning": 3, "afternoon": 4, "evening": 2}, ...}
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, ForeignKey, Boolean, Enum as SAEnum, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ScheduleMode(str, enum.Enum):
    TIME_SLOTS = "time_slots"   # Negocios con citas a hora exacta
    CAPACITY   = "capacity"     # Negocios por turno (mañana/tarde/noche)


class BusinessSchedule(Base):
    __tablename__ = "business_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    mode: Mapped[ScheduleMode] = mapped_column(
        SAEnum(ScheduleMode, name="schedulemode",
               values_callable=lambda e: [x.value for x in e],
               create_type=False),
        default=ScheduleMode.TIME_SLOTS,
        nullable=False,
    )

    # JSON con la disponibilidad semanal
    # time_slots:  {"monday": ["09:00","10:00"], "tuesday": ["09:00",...], ...}
    # capacity:    {"monday": {"morning":3,"afternoon":4}, ...}
    schedule_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Duración de cada cita en minutos (solo time_slots)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Días de anticipación máxima para agendar (ej: 30 días)
    max_days_ahead: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="schedule")

    def __repr__(self) -> str:
        return f"<BusinessSchedule business={self.business_id} mode={self.mode}>"
