import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Text, DateTime, Boolean, Integer, Numeric, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ServiceLog(Base):
    __tablename__ = "service_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # rating: 1-5, None si aún no ha respondido
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── KOS-54: Campos de cierre de servicio ─────────────────────────────────
    # Precio real cobrado (pre-cargado desde Service.ref_price, editable)
    price_charged: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Método de pago: efectivo | tarjeta | transferencia | otro
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Notas internas del servicio (qué se hizo, productos usados, etc.)
    service_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Si ya se envió el resumen/comprobante por WhatsApp al cliente
    summary_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="service_logs")
    client: Mapped["Client"] = relationship("Client", back_populates="service_logs")
    service: Mapped["Service"] = relationship("Service", back_populates="service_logs")

    def __repr__(self) -> str:
        return f"<ServiceLog client={self.client_id} service={self.service_id} rating={self.rating}>"
