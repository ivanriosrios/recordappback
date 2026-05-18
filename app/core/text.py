"""
Utilidades de normalización y parsing de texto compartidas.

Antes vivían duplicadas en webhooks.py, chatbot/engine.py y
chatbot/flows/booking.py — ahora hay una única fuente.
"""
import unicodedata


def normalize(text: str) -> str:
    """Lowercase + strip + sin acentos. Idempotente."""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def phone_suffix(raw: str, n: int = 10) -> str:
    """
    Sufijo de los últimos N dígitos del número, sin prefijos ni espacios.

    Útil para matching tolerante a formatos de WhatsApp/Twilio
    ("whatsapp:+57...", "+57 300...", "300...").
    """
    if not raw:
        return ""
    digits = "".join(c for c in raw if c.isdigit())
    return digits[-n:] if digits else ""


def strip_whatsapp_prefix(raw: str) -> str:
    """Limpia el prefijo `whatsapp:` de un número estilo Twilio."""
    if not raw:
        return ""
    return raw.replace("whatsapp:", "").strip()
