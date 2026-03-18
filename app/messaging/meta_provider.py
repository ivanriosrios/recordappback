"""
Implementación de MessagingProvider usando Meta WhatsApp Cloud API.

Esta es la implementación legacy que migra la lógica de app/services/whatsapp.py
al nuevo patrón de provider. Se mantiene para backward compatibility y como
fallback si se necesita volver a Meta directamente.

Ref: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import logging
import httpx

from app.messaging.base import MessagingProvider, MessageResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MetaProvider(MessagingProvider):
    """Proveedor de mensajería WhatsApp vía Meta Cloud API (legacy)."""

    BASE_URL = "https://graph.facebook.com/v22.0"

    def __init__(self):
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.token = settings.WHATSAPP_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _url(self) -> str:
        return f"{self.BASE_URL}/{self.phone_number_id}/messages"

    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es_CO",
        components: list | None = None,
        body_text: str | None = None,  # ignorado — Meta usa components
    ) -> MessageResult:
        """Envía un mensaje usando un template aprobado por Meta."""
        phone = self.normalize_phone(to)
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components

        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(self._url(), headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                wa_id = data.get("messages", [{}])[0].get("id", "")
                logger.info(
                    f"[Meta] Template '{template_name}' enviado a {phone} — wa_id={wa_id}"
                )
                return MessageResult(
                    success=True, message_id=wa_id, raw=data
                )
        except httpx.HTTPStatusError as e:
            body_text = e.response.text
            logger.error(f"[Meta] Error HTTP {e.response.status_code}: {body_text}")
            return MessageResult(
                success=False,
                error=f"{str(e)} — {body_text}",
                raw={"status_code": e.response.status_code},
            )
        except Exception as e:
            logger.error(f"[Meta] Error inesperado: {e}")
            return MessageResult(success=False, error=str(e))

    def send_text(self, to: str, body: str) -> MessageResult:
        """Envía un mensaje de texto simple vía Meta Cloud API."""
        phone = self.normalize_phone(to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(self._url(), headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                wa_id = data.get("messages", [{}])[0].get("id", "")
                logger.info(f"[Meta] Texto enviado a {phone} — wa_id={wa_id}")
                return MessageResult(
                    success=True, message_id=wa_id, raw=data
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"[Meta] Error HTTP {e.response.status_code}: {e.response.text}")
            return MessageResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"[Meta] Error inesperado: {e}")
            return MessageResult(success=False, error=str(e))
