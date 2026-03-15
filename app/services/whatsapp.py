"""
Servicio para interactuar con WhatsApp Cloud API (Meta).
Referencia: https://developers.facebook.com/docs/whatsapp/cloud-api
"""
import httpx
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppService:
    """Cliente para WhatsApp Cloud API."""

    BASE_URL = "https://graph.facebook.com/v21.0"

    def __init__(self):
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.token = settings.WHATSAPP_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _url(self) -> str:
        return f"{self.BASE_URL}/{self.phone_number_id}/messages"

    def _normalize_phone(self, phone: str) -> str:
        """Normaliza teléfono al formato E.164 sin el '+'. WhatsApp requiere solo dígitos."""
        digits = "".join(ch for ch in phone if ch.isdigit())
        # Elimina prefijo 00 si viene en ese formato
        if digits.startswith("00"):
            digits = digits[2:]
        if len(digits) < 9:
            raise ValueError("Número inválido: incluye indicativo de país (ej: 57...) y solo dígitos")
        return digits

    @staticmethod
    def build_body_components(*values: str) -> list:
        """
        Construye el array `components` para un template con variables en el BODY.
        Ejemplo: build_body_components("Juan", "Corte", "Barbería X")
        → [{"type": "body", "parameters": [{"type": "text", "text": "Juan"}, ...]}]
        """
        if not values:
            return []
        return [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in values],
            }
        ]

    def send_template(
        self,
        to: str,
        template_name: str = "hello_world",
        language_code: str = "en_US",
        components: list | None = None,
    ) -> dict:
        """
        Envía un mensaje usando un template aprobado por Meta.
        Para business-initiated conversations, WhatsApp requiere templates aprobados.
        """
        phone = self._normalize_phone(to)
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
                logger.info(f"[WhatsApp] Template '{template_name}' enviado a {phone} — wa_id={wa_id}")
                return {"success": True, "wa_message_id": wa_id, "raw": data}
        except httpx.HTTPStatusError as e:
            logger.error(f"[WhatsApp] Error HTTP {e.response.status_code}: {e.response.text}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"[WhatsApp] Error inesperado: {e}")
            return {"success": False, "error": str(e)}

    def send_text(self, to: str, body: str) -> dict:
        """
        Envía un mensaje de texto simple.
        Retorna la respuesta de la API con wa_message_id.
        """
        phone = self._normalize_phone(to)
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
                logger.info(f"[WhatsApp] Mensaje enviado a {phone} — wa_id={wa_id}")
                return {"success": True, "wa_message_id": wa_id, "raw": data}
        except httpx.HTTPStatusError as e:
            logger.error(f"[WhatsApp] Error HTTP {e.response.status_code}: {e.response.text}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"[WhatsApp] Error inesperado: {e}")
            return {"success": False, "error": str(e)}

    def render_template(
        self,
        template_body: str,
        client_name: str,
        service_name: str,
        business_name: str,
        extra: dict | None = None,
    ) -> str:
        """Reemplaza variables en el cuerpo del template."""
        text = template_body
        text = text.replace("{nombre_cliente}", client_name)
        text = text.replace("{servicio}", service_name)
        text = text.replace("{negocio}", business_name)
        if extra:
            for key, value in extra.items():
                text = text.replace(f"{{{key}}}", str(value))
        return text


# Instancia singleton
whatsapp = WhatsAppService()
