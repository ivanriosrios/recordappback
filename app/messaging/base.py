"""
Interfaz abstracta para proveedores de mensajería.

Cualquier proveedor (Meta, Twilio, futuro SMS gateway) debe implementar
esta interfaz. El resto del sistema solo conoce MessagingProvider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MessageResult:
    """Resultado estandarizado de envío de mensaje."""

    success: bool
    message_id: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)


class MessagingProvider(ABC):
    """Interfaz abstracta para proveedores de mensajería WhatsApp."""

    @abstractmethod
    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es_CO",
        components: list | None = None,
        body_text: str | None = None,
    ) -> MessageResult:
        """
        Envía un mensaje usando un template pre-aprobado.

        Args:
            to: Número de teléfono destino (E.164, ej: +573001234567)
            template_name: Nombre del template aprobado
            language_code: Código de idioma del template
            components: Parámetros del template (variables del body) — usado por MetaProvider
            body_text: Texto ya renderizado — usado por TwilioProvider como body directo

        Returns:
            MessageResult con success, message_id y detalles
        """
        ...

    @abstractmethod
    def send_text(self, to: str, body: str) -> MessageResult:
        """
        Envía un mensaje de texto libre.
        Solo funciona dentro de la ventana de 24h de conversación activa.

        Args:
            to: Número de teléfono destino
            body: Texto del mensaje

        Returns:
            MessageResult
        """
        ...

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normaliza teléfono: solo dígitos, sin +, sin espacios."""
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits.startswith("00"):
            digits = digits[2:]
        if len(digits) < 9:
            raise ValueError(
                "Número inválido: incluye indicativo de país (ej: 57...) y solo dígitos"
            )
        return digits

    @staticmethod
    def build_body_components(*values: str) -> list:
        """
        Construye el array de componentes para variables del BODY de un template.
        Compatible con formato Meta y mapeado internamente por cada provider.
        """
        if not values:
            return []
        return [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in values],
            }
        ]

    @staticmethod
    def render_template(
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
