import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Boolean, DateTime, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

import enum


class ChannelType(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class ClientStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OPTOUT = "optout"


class GenderType(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)       # apodo / nickname
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)   # nombre completo
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[GenderType | None] = mapped_column(SAEnum(GenderType), nullable=True)
    preferred_channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType), default=ChannelType.WHATSAPP, nullable=False)
    status: Mapped[ClientStatus] = mapped_column(SAEnum(ClientStatus), default=ClientStatus.ACTIVE, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="clients")
    reminders: Mapped[list["Reminder"]] = relationship("Reminder", back_populates="client", cascade="all, delete-orphan")
    service_logs: Mapped[list["ServiceLog"]] = relationship("ServiceLog", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Client {self.display_name}>"
