from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from app.models.client import ChannelType, ClientStatus


class ClientCreate(BaseModel):
    display_name: str
    phone: str
    email: str | None = None
    preferred_channel: ChannelType = ChannelType.WHATSAPP
    notes: str | None = None

    @field_validator("preferred_channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        if v is None:
            return ChannelType.WHATSAPP
        val = str(v).lower()
        return ChannelType(val) if val in {c.value for c in ChannelType} else ChannelType.WHATSAPP


class ClientUpdate(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    preferred_channel: ChannelType | None = None
    status: ClientStatus | None = None
    notes: str | None = None

    @field_validator("preferred_channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return ChannelType(val) if val in {c.value for c in ChannelType} else ChannelType.WHATSAPP

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if v is None:
            return v
        val = str(v).lower()
        return ClientStatus(val) if val in {s.value for s in ClientStatus} else ClientStatus.ACTIVE


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
