from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.client import ChannelType, ClientStatus


class ClientCreate(BaseModel):
    display_name: str
    phone: str
    email: str | None = None
    preferred_channel: ChannelType = ChannelType.WHATSAPP
    notes: str | None = None


class ClientUpdate(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    preferred_channel: ChannelType | None = None
    status: ClientStatus | None = None
    notes: str | None = None


class ClientResponse(BaseModel):
    id: UUID
    business_id: UUID
    display_name: str
    phone: str
    email: str | None
    preferred_channel: ChannelType
    status: ClientStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
