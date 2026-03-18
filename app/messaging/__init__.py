"""
Capa abstracta de mensajería para RecordApp.

Este módulo es un transport layer puro — NO importa de api/, tasks/ o models/.
Provee una interfaz unificada para enviar mensajes por WhatsApp
independientemente del proveedor (Meta Cloud API o Twilio).

Uso:
    from app.messaging import get_messaging_provider
    provider = get_messaging_provider()
    result = provider.send_template(to="+573001234567", template_name="recordatorio_cita", ...)
"""

from app.messaging.base import MessagingProvider, MessageResult
from app.messaging.factory import get_messaging_provider

__all__ = ["MessagingProvider", "MessageResult", "get_messaging_provider"]
