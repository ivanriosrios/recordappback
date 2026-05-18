"""
Anticipo (seña) que un cliente paga al confirmar una cita.

Reduce no-shows: el dueño configura el % o monto fijo y el chatbot
envía un link de pago de MercadoPago al confirmar el booking.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ClientPaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class ClientPayment(Base):
    __tablename__ = "client_payments"
    __table_args__ = (
        Index("ix_client_payments_business", "business_id"),
        Index("ix_client_payments_appointment", "appointment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[ClientPaymentStatus] = mapped_column(
        SAEnum(ClientPaymentStatus, name="clientpaymentstatus",
               values_callable=lambda e: [x.value for x in e],
               create_type=True),
        default=ClientPaymentStatus.PENDING,
        nullable=False,
    )

    mp_preference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mp_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    init_point: Mapped[str | None] = mapped_column(String(500), nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
