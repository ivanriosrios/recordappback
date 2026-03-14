from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from app.models.business import PlanType


class BusinessCreate(BaseModel):
    name: str
    business_type: str = "general"
    whatsapp_phone: str
    email: str | None = None
    password: str | None = None
    plan: PlanType | None = None


class BusinessUpdate(BaseModel):
    name: str | None = None
    business_type: str | None = None
    whatsapp_phone: str | None = None
    logo_url: str | None = None


class BusinessResponse(BaseModel):
    id: UUID
    name: str
    business_type: str
    whatsapp_phone: str
    email: str | None
    plan: PlanType
    logo_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
