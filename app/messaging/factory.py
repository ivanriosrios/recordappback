"""
Factory para seleccionar el proveedor de mensajería activo.

El proveedor se determina por la variable de entorno MESSAGING_PROVIDER.
Cambiar de proveedor es tan simple como cambiar esa variable — sin tocar código.
"""

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.messaging.base import MessagingProvider

logger = logging.getLogger(__name__)


@lru_cache
def get_messaging_provider() -> MessagingProvider:
    """
    Retorna la instancia singleton del proveedor de mensajería configurado.

    Returns:
        MessagingProvider — TwilioProvider o MetaProvider según config.
    """
    settings = get_settings()
    provider_name = settings.MESSAGING_PROVIDER.lower().strip()

    if provider_name == "twilio":
        from app.messaging.twilio_provider import TwilioProvider

        logger.info("[messaging] Proveedor activo: Twilio")
        return TwilioProvider()

    elif provider_name == "meta":
        from app.messaging.meta_provider import MetaProvider

        logger.info("[messaging] Proveedor activo: Meta WhatsApp Cloud API")
        return MetaProvider()

    else:
        raise ValueError(
            f"Proveedor de mensajería '{provider_name}' no soportado. "
            f"Usa 'twilio' o 'meta' en MESSAGING_PROVIDER."
        )
