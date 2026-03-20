import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class WhatsAppStatus(str, enum.Enum):
    NOT_CONFIGURED = "not_configured"  # Nunca configurado
    SANDBOX = "sandbox"                # Usando sandbox de Twilio para pruebas
    ACTIVE = "active"                  # WhatsApp Business API aprobado y activo


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint("email", name="uq_businesses_email"),
        UniqueConstraint("whatsapp_phone", name="uq_businesses_whatsapp_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    business_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    whatsapp_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Use enum values (lowercase) to match DB enum definition
    plan: Mapped[PlanType] = mapped_column(
        SAEnum(PlanType, name="plantype", values_callable=lambda enum_cls: [e.value for e in enum_cls], create_type=False),
        default=PlanType.FREE,
        nullable=False,
    )
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Estado de configuración de WhatsApp Business
    whatsapp_status: Mapped[WhatsAppStatus] = mapped_column(
        SAEnum(WhatsAppStatus, name="whatsappstatus", values_callable=lambda e: [x.value for x in e], create_type=False),
        default=WhatsAppStatus.NOT_CONFIGURED,
        nullable=False,
        server_default="not_configured",
    )

    # Automation settings (configurable per business)
    inactive_days_threshold: Mapped[int] = mapped_column(default=60, nullable=False, server_default="60")
    reactivation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    birthday_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    follow_up_auto_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")

    # Relationships
    clients: Mapped[list["Client"]] = relationship("Client", back_populates="business", cascade="all, delete-orphan")
    services: Mapped[list["Service"]] = relationship("Service", back_populates="business", cascade="all, delete-orphan")
    templates: Mapped[list["Template"]] = relationship("Template", back_populates="business", cascade="all, delete-orphan")
    service_logs: Mapped[list["ServiceLog"]] = relationship("ServiceLog", back_populates="business", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    schedule: Mapped["BusinessSchedule | None"] = relationship("BusinessSchedule", back_populates="business", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Business {self.name}>"
