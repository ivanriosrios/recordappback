from pydantic import BaseModel, field_validator
from uuid import UUID
from app.models.template import TemplateType, TemplateChannel, TemplateStatus


class TemplateCreate(BaseModel):
    """Solo para uso interno / admin. Los usuarios no crean templates."""
    name: str
    body: str
    type: TemplateType = TemplateType.REMINDER
    channel: TemplateChannel = TemplateChannel.WHATSAPP
    meta_template_name: str | None = None
    meta_language_code: str = "es"

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if v is None:
            return TemplateType.REMINDER
        val = str(v).lower()
        return TemplateType(val) if val in {t.value for t in TemplateType} else TemplateType.REMINDER

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        if v is None:
            return TemplateChannel.WHATSAPP
        val = str(v).lower()
        return TemplateChannel(val) if val in {c.value for c in TemplateChannel} else TemplateChannel.WHATSAPP


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    type: TemplateType | None = None
    channel: TemplateChannel | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return TemplateType(val) if val in {t.value for t in TemplateType} else TemplateType.REMINDER

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return TemplateChannel(val) if val in {c.value for c in TemplateChannel} else TemplateChannel.WHATSAPP


class TemplateResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    body: str
    type: TemplateType
    channel: TemplateChannel
    meta_template_name: str | None = None
    meta_language_code: str = "es"
    status: TemplateStatus = TemplateStatus.APPROVED
    is_system: bool = False

    model_config = {"from_attributes": True}
