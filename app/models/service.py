import uuid
from sqlalchemy import String, Text, Boolean, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from decimal import Decimal

from app.core.database import Base


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # días después del servicio para enviar encuesta
    # KOS-54: duración estimada (minutos) — mostrada en el formulario de cierre
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="services")
    reminders: Mapped[list["Reminder"]] = relationship("Reminder", back_populates="service")
    service_logs: Mapped[list["ServiceLog"]] = relationship("ServiceLog", back_populates="service")
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="service")

    def __repr__(self) -> str:
        return f"<Service {self.name}>"
