"""
Modelo Appointment — cita agendada por un cliente a través del chatbot.

Flujo de estados:
  requested → confirmed → completed
  requested → rejected
  requested/confirmed → cancelled
"""
import uuid
import enum
from datetime import datetime, date

from sqlalchemy import String, Text, ForeignKey, DateTime, Date, Time, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    REQUESTED  = "requested"   # Cliente solicitó via chatbot, esperando confirmación
    CONFIRMED  = "confirmed"   # Negocio confirmó
    REJECTED   = "rejected"    # Negocio rechazó
    COMPLETED  = "completed"   # Servicio realizado
    CANCELLED  = "cancelled"   # Cancelado (por cliente o negocio)


class AppointmentShift(str, enum.Enum):
    """Turno para mode=capacity."""
    MORNING   = "morning"    # Mañana
    AFTERNOON = "afternoon"  # Tarde
    EVENING   = "evening"    # Noche


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointmentstatus",
               values_callable=lambda e: [x.value for x in e],
               create_type=False),
        default=AppointmentStatus.REQUESTED,
        nullable=False,
    )

    # Fecha de la cita
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Solo para mode=time_slots (hora exacta, ej: "10:00")
    appointment_time: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Solo para mode=capacity (turno)
    shift: Mapped[AppointmentShift | None] = mapped_column(
        SAEnum(AppointmentShift, name="appointmentshift",
               values_callable=lambda e: [x.value for x in e],
               create_type=False),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps de gestión
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="appointments")
    client:   Mapped["Client"]   = relationship("Client",   back_populates="appointments")
    service:  Mapped["Service"]  = relationship("Service",  back_populates="appointments")

    def __repr__(self) -> str:
        return f"<Appointment {self.id} client={self.client_id} date={self.appointment_date} status={self.status}>"
