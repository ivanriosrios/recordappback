from pydantic import BaseModel
from uuid import UUID
from app.models.template import TemplateType, TemplateChannel


class TemplateCreate(BaseModel):
    name: str
    body: str
    type: TemplateType = TemplateType.REMINDER
    channel: TemplateChannel = TemplateChannel.WHATSAPP


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    type: TemplateType | None = None
    channel: TemplateChannel | None = None


class TemplateResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    body: str
    type: TemplateType
    channel: TemplateChannel

    model_config = {"from_attributes": True}
