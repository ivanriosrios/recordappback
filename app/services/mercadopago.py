"""
Wrapper minimalista de la API REST de MercadoPago.

Solo se usan dos endpoints:

1. **Preapproval** (suscripción recurrente) — autoriza un cobro mensual
   en la tarjeta del usuario. Usado para el SaaS.
   Doc: https://www.mercadopago.com.co/developers/es/reference/subscriptions/_preapproval/post

2. **Preference** (pago único) — genera un link/QR de checkout.
   Usado para los anticipos del cliente final.
   Doc: https://www.mercadopago.com.co/developers/es/reference/preferences/_checkout_preferences/post

Diseño:
  - HTTP síncrono (usado desde endpoints async via to_thread si fuese
    necesario; en MVP las llamadas son rápidas y los endpoints son
    pocos, así que se invocan dentro de async sin penalty notable).
  - Errores se propagan como `MercadoPagoError`. No reintenta — el
    caller decide.
  - Si no hay `MP_ACCESS_TOKEN`, las funciones lanzan inmediatamente.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MercadoPagoError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _headers() -> dict[str, str]:
    if not settings.MP_ACCESS_TOKEN:
        raise MercadoPagoError("MP_ACCESS_TOKEN no configurado")
    return {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    url = f"{settings.MP_BASE_URL}{path}"
    r = requests.post(url, json=payload, headers=_headers(), timeout=15)
    if r.status_code >= 400:
        logger.warning(f"[mp] POST {path} -> {r.status_code} {r.text[:300]}")
        raise MercadoPagoError(
            f"MP {path} fallo {r.status_code}", status=r.status_code, body=r.text
        )
    return r.json()


def _get(path: str) -> dict:
    url = f"{settings.MP_BASE_URL}{path}"
    r = requests.get(url, headers=_headers(), timeout=15)
    if r.status_code >= 400:
        logger.warning(f"[mp] GET {path} -> {r.status_code} {r.text[:300]}")
        raise MercadoPagoError(
            f"MP {path} fallo {r.status_code}", status=r.status_code, body=r.text
        )
    return r.json()


# ──────────────────────────────────────────────────────────────────────
# Suscripción SaaS (preapproval)
# ──────────────────────────────────────────────────────────────────────

def create_preapproval(
    *,
    payer_email: str,
    amount: float,
    reason: str,
    back_url: str,
    external_reference: str,
    currency: str = "USD",
    trial_days: int = 0,
) -> dict:
    """
    Crea una autorización de cobro recurrente mensual.
    Devuelve el dict del preapproval; el frontend redirige a `init_point`.
    """
    from datetime import datetime, timedelta, timezone

    payload: dict[str, Any] = {
        "reason": reason,
        "external_reference": external_reference,
        "payer_email": payer_email,
        "back_url": back_url,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(amount),
            "currency_id": currency,
        },
        "status": "pending",
    }
    if trial_days > 0:
        # Primer cobro tras N días → start_date en el futuro.
        start = datetime.now(timezone.utc) + timedelta(days=trial_days)
        payload["auto_recurring"]["start_date"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return _post("/preapproval", payload)


def get_preapproval(preapproval_id: str) -> dict:
    return _get(f"/preapproval/{preapproval_id}")


def cancel_preapproval(preapproval_id: str) -> dict:
    """Cancela un preapproval activo."""
    payload = {"status": "cancelled"}
    url = f"/preapproval/{preapproval_id}"
    r = requests.put(
        f"{settings.MP_BASE_URL}{url}",
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    if r.status_code >= 400:
        raise MercadoPagoError(
            f"MP cancel {url} fallo {r.status_code}", status=r.status_code, body=r.text
        )
    return r.json()


# ──────────────────────────────────────────────────────────────────────
# Anticipo cliente final (preference)
# ──────────────────────────────────────────────────────────────────────

def create_deposit_preference(
    *,
    title: str,
    amount: float,
    currency: str,
    external_reference: str,
    notification_url: str,
    success_url: str,
) -> dict:
    payload = {
        "items": [
            {
                "title": title[:250],
                "quantity": 1,
                "unit_price": float(amount),
                "currency_id": currency,
            }
        ],
        "external_reference": external_reference,
        "notification_url": notification_url,
        "back_urls": {
            "success": success_url,
            "failure": success_url,
            "pending": success_url,
        },
        "auto_return": "approved",
    }
    return _post("/checkout/preferences", payload)


def get_payment(payment_id: str) -> dict:
    """Detalle de un payment de MP (usado desde el webhook)."""
    return _get(f"/v1/payments/{payment_id}")
