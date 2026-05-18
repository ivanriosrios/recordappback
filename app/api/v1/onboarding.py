"""
Onboarding wizard — endpoint para enviar el mensaje de prueba al final.

El frontend lo invoca al cerrar el wizard. Envia un WhatsApp "demo"
al primer cliente registrado del negocio. Si el negocio no tiene un
cliente todavía, devuelve 400.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client
from app.messaging import get_messaging_provider
from app.services.messaging_format import prefix_business

router = APIRouter(prefix="/businesses/{business_id}/onboarding", tags=["onboarding"])


class TestMessageRequest(BaseModel):
    client_id: UUID | None = None
    body: str | None = None


@router.post("/test-message")
async def send_test_message(
    business_id: UUID,
    payload: TestMessageRequest,
    biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    # Cliente destino: el del payload o el primero registrado
    if payload.client_id:
        client = (
            await db.execute(
                select(Client).where(Client.id == payload.client_id, Client.business_id == business_id)
            )
        ).scalar_one_or_none()
    else:
        client = (
            await db.execute(
                select(Client)
                .where(Client.business_id == business_id)
                .where(Client.deleted_at.is_(None))
                .order_by(desc(Client.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Aún no tienes clientes para enviar el mensaje de prueba")

    text = payload.body or (
        f"¡Hola {client.display_name}! 👋\n\n"
        f"Soy {biz.name}. Te escribo desde RecordApp para confirmar que ya estamos "
        f"conectados por WhatsApp. A partir de ahora te avisaremos de citas, "
        f"recordatorios y promociones por aquí. 🙌"
    )
    body = prefix_business(biz.name, text)

    provider = get_messaging_provider()
    result = provider.send_text(to=client.phone, body=body)
    if not result.success:
        raise HTTPException(status_code=502, detail=f"No se pudo enviar: {result.error}")
    return {
        "sent_to": client.phone,
        "client_id": str(client.id),
        "message_id": result.message_id,
    }
