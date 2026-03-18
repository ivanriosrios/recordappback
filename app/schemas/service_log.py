from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field


class ServiceLogCreate(BaseModel):
    client_id: UUID
    service_id: UUID
    notes: str | None = None


class ServiceLogComplete(BaseModel):
    """Payload para cerrar un servicio con precio, pago y notas."""
    price_charged: Decimal | None = None
    payment_method: str | None = None   # efectivo | tarjeta | transferencia | otro
    service_notes: str | None = None
    notes: str | None = None            # notas generales (actualiza el campo existente)
    send_summary: bool = False          # si True → envía resumen por WhatsApp al cliente


class ServiceLogResponse(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    service_id: UUID
    completed_at: datetime
    notes: str | None
    follow_up_sent: bool
    rating: int | None = Field(None, ge=1, le=5)

    # KOS-54
    price_charged: Decimal | None = None
    payment_method: str | None = None
    service_notes: str | None = None
    summary_sent: bool = False

    # Datos derivados para el frontend
    client_name: str | None = None
    service_name: str | None = None

    model_config = {"from_attributes": True}
