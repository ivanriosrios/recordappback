from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ServiceLogCreate(BaseModel):
    client_id: UUID
    service_id: UUID
    notes: str | None = None


class ServiceLogResponse(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    service_id: UUID
    completed_at: datetime
    notes: str | None
    follow_up_sent: bool
    rating: int | None = Field(None, ge=1, le=5)

    # Datos derivados para el frontend
    client_name: str | None = None
    service_name: str | None = None

    model_config = {"from_attributes": True}
