from fastapi import APIRouter, Request, Query, HTTPException
from app.core.config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

settings = get_settings()


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """Verificación del webhook de Meta WhatsApp Cloud API."""
    if hub_mode == "subscribe" and hub_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@router.post("/whatsapp")
async def receive_webhook(request: Request):
    """Recibe eventos de WhatsApp (mensajes, status updates).

    TODO: Implementar en Ciclo 3:
    - Parsear respuestas de clientes (botón Sí/No)
    - Actualizar ReminderLog
    - Notificar al negocio
    - Manejar opt-out
    """
    body = await request.json()

    # Por ahora solo logueamos el evento
    # En Ciclo 3 se implementa la lógica completa
    print(f"[WhatsApp Webhook] Evento recibido: {body}")

    return {"status": "ok"}
