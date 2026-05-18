"""
Clasificación de intents para mensajes entrantes de WhatsApp.

Dos modos:
- Determinista por keywords (default, sin dependencias externas).
- LLM (Claude Haiku) si LLM_INTENT_CLASSIFIER_ENABLED=True y hay API key.
  El LLM es un *complemento*: solo se invoca cuando el clasificador
  determinista devuelve `unknown`, para no añadir latencia ni costo
  cuando ya hay match claro.

Intents soportados:
    "optout" | "booking_intent" | "rated_good" | "rated_bad" |
    "responded_yes" | "responded_no" | "unknown"
"""
from __future__ import annotations

import logging
from typing import Literal

from app.core.config import get_settings
from app.core.text import normalize

logger = logging.getLogger(__name__)
settings = get_settings()

Intent = Literal[
    "optout", "booking_intent", "rated_good", "rated_bad",
    "responded_yes", "responded_no", "unknown",
]

POSITIVE_KEYWORDS = {"si", "sí", "yes", "ok", "claro", "dale", "listo", "confirmo"}
NEGATIVE_KEYWORDS = {"no", "nop", "cancelar", "cancel"}
GOOD_KEYWORDS = {"bien", "buen", "excelente", "bueno", "good", "perfecto", "genial", "1", "2"}
BAD_KEYWORDS = {"mal", "malo", "mala", "bad", "pesimo", "regular", "3", "4"}
OPTOUT_KEYWORDS = {"salir", "baja", "stop", "unsubscribe", "no quiero", "no mas"}
# NOTE: keywords ambiguas como "si"/"sí"/"yes" se evitan a propósito:
# solo el ChatbotEngine las trata como confirmación cuando hay un flujo activo.
BOOKING_KEYWORDS = {
    "cita", "agendar", "reservar", "turno", "quiero cita", "quiero turno",
    "hora", "appointment", "book", "reserva", "cuando", "disponible", "agenda",
}


def _rule_based(text: str) -> Intent:
    t = normalize(text)
    words = set(t.split())
    if words & OPTOUT_KEYWORDS or any(k in t for k in OPTOUT_KEYWORDS):
        return "optout"
    if any(k in t for k in BOOKING_KEYWORDS):
        return "booking_intent"
    if words & GOOD_KEYWORDS or any(k in t for k in GOOD_KEYWORDS):
        return "rated_good"
    if words & BAD_KEYWORDS or any(k in t for k in BAD_KEYWORDS):
        return "rated_bad"
    if words & POSITIVE_KEYWORDS:
        return "responded_yes"
    if words & NEGATIVE_KEYWORDS:
        return "responded_no"
    return "unknown"


_LLM_SYSTEM = (
    "Eres un clasificador de mensajes cortos de WhatsApp en español "
    "para un negocio de servicios. Devuelve EXACTAMENTE una etiqueta "
    "de esta lista, en minúsculas y sin comillas: "
    "optout, booking_intent, rated_good, rated_bad, responded_yes, "
    "responded_no, unknown. Sin texto adicional."
)
_VALID: set[Intent] = {
    "optout", "booking_intent", "rated_good", "rated_bad",
    "responded_yes", "responded_no", "unknown",
}


def _llm_fallback(text: str) -> Intent:
    """
    Consulta a Claude Haiku. Se invoca SOLO cuando el clasificador
    determinista devuelve `unknown` y el flag está activo. Si algo
    falla, regresa `unknown` (degrada elegantemente).
    """
    try:
        # Import perezoso para no obligar a tener anthropic instalado.
        from anthropic import Anthropic  # type: ignore
    except Exception:
        logger.info("[intent] anthropic no instalado, skip LLM fallback")
        return "unknown"

    if not settings.ANTHROPIC_API_KEY:
        return "unknown"

    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=10,
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": text[:280]}],
        )
        label = (resp.content[0].text or "").strip().lower()
        return label if label in _VALID else "unknown"  # type: ignore[return-value]
    except Exception as exc:
        logger.warning(f"[intent] LLM fallback falló: {exc}")
        return "unknown"


def classify(text: str) -> Intent:
    """
    Punto de entrada. Determinista primero, LLM opcional como fallback.
    """
    intent = _rule_based(text)
    if intent != "unknown":
        return intent
    if settings.LLM_INTENT_CLASSIFIER_ENABLED:
        return _llm_fallback(text)
    return intent
