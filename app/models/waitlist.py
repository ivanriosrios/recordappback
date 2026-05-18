"""
WaitlistEntry — cliente esperando un cupo cuando no hay disponibilidad.

Cuando una cita se libera (cancelada por cliente, auto-cancelada por no
confirmar, no-show marcado por el negocio), una tarea Celery busca el
primer match en la waitlist por servicio + fecha/turno preferido y
ofrece el slot por WhatsApp. Si el cliente acepta, se crea Appointment
con `rescued_from_waitlist=True`.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import DateTime, ForeignKey, Date, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.models.appointment import AppointmentShift


class WaitlistStatus(str, enum.Enum):
    PENDING  = "pending"   # Esperando que se libere un cupo
    OFFERED  = "offered"   # Se le ofreció un slot, esperando respuesta
    ACCEPTED = "accepted"  # Aceptó, ya tiene appointment
    DECLINED = "declined"  # Rechazó la oferta
    EXPIRED  = "expired"   # No respondió en la ventana
    REMOVED  = "removed"   # Sacado manualmente por el negocio


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        Index("ix_waitlist_business_status", "business_id", "status"),
        Index("ix_waitlist_client", "client_id"),
    )

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

    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_shift: Mapped[AppointmentShift | None] = mapped_column(
        SAEnum(AppointmentShift, name="appointmentshift",
               values_callable=lambda e: [x.value for x in e],
               create_type=False),
        nullable=True,
    )

    status: Mapped[WaitlistStatus] = mapped_column(
        SAEnum(WaitlistStatus, name="waitliststatus",
               values_callable=lambda e: [x.value for x in e],
               create_type=True),
        default=WaitlistStatus.PENDING,
        nullable=False,
    )

    # Oferta activa: se llena cuando le ofrecimos un slot.
    offered_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    offered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<WaitlistEntry biz={self.business_id} client={self.client_id} status={self.status}>"
