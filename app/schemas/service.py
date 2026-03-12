from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    ref_price: Decimal | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    ref_price: Decimal | None = None
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    description: str | None
    ref_price: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}
