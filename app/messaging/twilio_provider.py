"""
Implementación de MessagingProvider usando Twilio WhatsApp API.

Twilio usa Content Templates para WhatsApp. Los templates se registran
en la consola de Twilio y se referencian por content_sid o directamente
con el nombre del template de Meta (Twilio hace el bridge).

Ref: https://www.twilio.com/docs/messaging/guides/how-to-use-your-free-trial-account
     https://www.twilio.com/docs/messaging/whatsapp
"""

import logging
from twilio.rest import Client as TwilioClient

from app.messaging.base import MessagingProvider, MessageResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioProvider(MessagingProvider):
    """Proveedor de mensajería WhatsApp vía Twilio."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.api_key_sid = settings.TWILIO_API_KEY_SID
        self.api_key_secret = settings.TWILIO_API_KEY_SECRET
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER  # whatsapp:+1234567890

        # Twilio client con API Key (más seguro que Auth Token)
        self.client = TwilioClient(
            self.api_key_sid,
            self.api_key_secret,
            self.account_sid,
        )

    def _whatsapp_to(self, phone: str) -> str:
        """Formatea el número destino para Twilio WhatsApp: whatsapp:+<digits>."""
        digits = self.normalize_phone(phone)
        return f"whatsapp:+{digits}"

    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es_CO",
        components: list | None = None,
    ) -> MessageResult:
        """
        Envía un template de WhatsApp vía Twilio.

        Twilio usa Content Templates (content_sid) o puede enviar templates
        de Meta directamente si están registrados en la cuenta.
        Para máxima compatibilidad, usamos el approach de content variables.
        """
        wa_to = self._whatsapp_to(to)

        try:
            # Extraer variables del body de los components (formato Meta)
            content_variables = {}
            if components:
                for comp in components:
                    if comp.get("type") == "body":
                        for idx, param in enumerate(comp.get("parameters", []), start=1):
                            content_variables[str(idx)] = param.get("text", "")

            # Construir kwargs del mensaje
            message_kwargs = {
                "from_": self.from_number,
                "to": wa_to,
            }

            if content_variables:
                # Enviar como template con variables usando ContentSid
                # Si el template está mapeado como Content Template en Twilio:
                import json

                message_kwargs["content_variables"] = json.dumps(content_variables)
                # Usamos body como fallback — Twilio lo acepta para templates
                # cuando no se tiene content_sid y se usa el sandbox
                body_parts = [content_variables[k] for k in sorted(content_variables.keys())]
                message_kwargs["body"] = (
                    f"[Template: {template_name}] " + " | ".join(body_parts)
                )
            else:
                message_kwargs["body"] = f"[Template: {template_name}]"

            message = self.client.messages.create(**message_kwargs)

            logger.info(
                f"[Twilio] Template '{template_name}' enviado a {wa_to} — sid={message.sid}"
            )
            return MessageResult(
                success=True,
                message_id=message.sid,
                raw={
                    "sid": message.sid,
                    "status": message.status,
                    "to": wa_to,
                    "template_name": template_name,
                },
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Twilio] Error enviando template '{template_name}' a {wa_to}: {error_msg}")
            return MessageResult(
                success=False,
                error=error_msg,
                raw={"to": wa_to, "template_name": template_name},
            )

    def send_text(self, to: str, body: str) -> MessageResult:
        """Envía un mensaje de texto libre por WhatsApp vía Twilio."""
        wa_to = self._whatsapp_to(to)

        try:
            message = self.client.messages.create(
                from_=self.from_number,
                to=wa_to,
                body=body,
            )

            logger.info(f"[Twilio] Texto enviado a {wa_to} — sid={message.sid}")
            return MessageResult(
                success=True,
                message_id=message.sid,
                raw={"sid": message.sid, "status": message.status},
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Twilio] Error enviando texto a {wa_to}: {error_msg}")
            return MessageResult(success=False, error=error_msg)
