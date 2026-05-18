"""
Lógica de ciclo de vida de Subscription.

Cubre:
- alta con trial (crear en MP preapproval + DB)
- transición a active al recibir webhook de cobro aprobado
- marcar past_due / cancel al recibir cobros rechazados
- admin: granted_free_months, reactivate
- helpers de acceso (gating)

Las llamadas de MP están encapsuladas en `app.services.mercadopago`.
Aquí solo hablamos de dominio.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import get_settings
from app.models.business import Business
from app.models.subscription import (
    Subscription,
    SubscriptionStatus,
    SaasPayment,
)
from app.services import mercadopago as mp

logger = logging.getLogger(__name__)
settings = get_settings()


def _now() -> datetime:
    return datetime.utcnow()


# ──────────────────────────────────────────────────────────────────────
# Async (FastAPI handlers)
# ──────────────────────────────────────────────────────────────────────

async def get_or_create_subscription(db: AsyncSession, business: Business) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.business_id == business.id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub
    trial_end = _now() + timedelta(days=settings.SAAS_TRIAL_DAYS)
    sub = Subscription(
        business_id=business.id,
        status=SubscriptionStatus.TRIALING,
        plan_name=settings.SAAS_PLAN_NAME,
        price_usd=settings.SAAS_PRICE_USD,
        currency=settings.SAAS_CURRENCY,
        trial_ends_at=trial_end,
        current_period_end=trial_end,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


async def start_checkout(db: AsyncSession, business: Business, payer_email: str) -> Subscription:
    """
    Llama a MercadoPago para crear el preapproval y deja el negocio listo
    para redirigir al `init_point`.
    """
    sub = await get_or_create_subscription(db, business)
    back_url = f"{settings.APP_BASE_URL}/billing/return"
    preapproval = mp.create_preapproval(
        payer_email=payer_email,
        amount=float(sub.price_usd),
        reason=f"RecordApp · {sub.plan_name}",
        back_url=back_url,
        external_reference=str(sub.id),
        currency=sub.currency,
        trial_days=settings.SAAS_TRIAL_DAYS,
    )
    sub.mp_preapproval_id = preapproval.get("id")
    sub.mp_payer_email = payer_email
    sub.mp_init_point = preapproval.get("init_point") or preapproval.get("sandbox_init_point")
    await db.flush()
    await db.refresh(sub)
    return sub


async def cancel(db: AsyncSession, sub: Subscription) -> Subscription:
    if sub.mp_preapproval_id:
        try:
            mp.cancel_preapproval(sub.mp_preapproval_id)
        except mp.MercadoPagoError as exc:
            logger.warning(f"[sub] cancel MP falló (sigue local): {exc}")
    sub.status = SubscriptionStatus.CANCELED
    sub.canceled_at = _now()
    await db.flush()
    await db.refresh(sub)
    return sub


# ──────────────────────────────────────────────────────────────────────
# Sync — para webhooks y tareas Celery
# ──────────────────────────────────────────────────────────────────────

def apply_payment_sync(
    session: Session,
    *,
    subscription_id: str | None,
    mp_payment_id: str,
    amount: float,
    currency: str,
    status: str,
) -> SaasPayment | None:
    """
    Registra un payment recibido vía webhook y avanza el estado de la sub.
    `status` es el del payment de MP: approved/rejected/pending/refunded/...
    """
    if not subscription_id:
        logger.warning(f"[sub] payment {mp_payment_id} sin external_reference")
        return None

    sub = session.get(Subscription, subscription_id)
    if not sub:
        logger.warning(f"[sub] subscription {subscription_id} no encontrada")
        return None

    payment = SaasPayment(
        subscription_id=sub.id,
        mp_payment_id=mp_payment_id,
        amount=amount,
        currency=currency,
        status=status,
        paid_at=_now() if status == "approved" else None,
    )
    session.add(payment)

    if status == "approved":
        sub.status = SubscriptionStatus.ACTIVE
        base = sub.current_period_end or _now()
        if base < _now():
            base = _now()
        sub.current_period_end = base + timedelta(days=30)
        sub.canceled_at = None
    elif status == "rejected":
        sub.status = SubscriptionStatus.PAST_DUE
    elif status in ("refunded", "charged_back"):
        # Mantén acceso si ya estaba activo, pero registra el evento.
        pass

    session.flush()
    return payment


# ──────────────────────────────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────────────────────────────

def admin_grant_free_month(session: Session, sub: Subscription, months: int = 1) -> Subscription:
    """Extiende current_period_end por N meses y mueve a estado FREE si aplica."""
    base = sub.current_period_end or _now()
    if base < _now():
        base = _now()
    sub.current_period_end = base + timedelta(days=30 * max(1, months))
    sub.granted_free_months += max(1, months)
    if sub.status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED):
        sub.status = SubscriptionStatus.FREE
    session.flush()
    return sub


def admin_reactivate(session: Session, sub: Subscription) -> Subscription:
    """
    Re-activa una suscripción cancelada o past_due. Si tenía cortesías,
    queda como FREE; si no, vuelve a TRIALING por SAAS_TRIAL_DAYS días.
    """
    if sub.status == SubscriptionStatus.ACTIVE:
        return sub
    sub.canceled_at = None
    if sub.granted_free_months > 0 and (sub.current_period_end or _now()) > _now():
        sub.status = SubscriptionStatus.FREE
    else:
        sub.status = SubscriptionStatus.TRIALING
        sub.trial_ends_at = _now() + timedelta(days=settings.SAAS_TRIAL_DAYS)
        sub.current_period_end = sub.trial_ends_at
    session.flush()
    return sub


def admin_suspend(session: Session, sub: Subscription) -> Subscription:
    sub.status = SubscriptionStatus.CANCELED
    sub.canceled_at = _now()
    session.flush()
    return sub
