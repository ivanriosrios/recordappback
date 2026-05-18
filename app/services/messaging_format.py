"""
Formato de mensajes salientes.

En modo SHARED_WHATSAPP_MODE (un solo número Twilio para todos los
negocios), prefijamos el body con el nombre del negocio para que el
destinatario sepa de quién es. Cuando cada negocio tiene su propio
número, el prefijo no aporta y se desactiva.
"""
from app.core.config import get_settings

settings = get_settings()


def prefix_business(business_name: str | None, body: str) -> str:
    if not settings.SHARED_WHATSAPP_MODE or not business_name:
        return body
    return f"*{business_name}*\n\n{body}"
