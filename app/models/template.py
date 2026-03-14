import uuid
from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

import enum


class TemplateType(str, enum.Enum):
    REMINDER = "reminder"
    PROMO = "promo"
    REACTIVATION = "reactivation"
    FOLLOW_UP = "follow_up"    # encuesta post-servicio
    BIRTHDAY = "birthday"      # felicitación cumpleaños


class TemplateChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[TemplateType] = mapped_column(
        SAEnum(TemplateType, name="templatetype", values_callable=lambda enum_cls: [e.value for e in enum_cls], create_type=False),
        default=TemplateType.REMINDER,
        nullable=False,
    )
    channel: Mapped[TemplateChannel] = mapped_column(
        SAEnum(TemplateChannel, name="templatechannel", values_callable=lambda enum_cls: [e.value for e in enum_cls], create_type=False),
        default=TemplateChannel.WHATSAPP,
        nullable=False,
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="templates")
    reminders: Mapped[list["Reminder"]] = relationship("Reminder", back_populates="template")

    def __repr__(self) -> str:
        return f"<Template {self.name}>"
