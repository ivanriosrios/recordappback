"""
Endpoints de billing del SaaS.

Flujo:
  POST /billing/me/checkout    → crea preapproval en MP, devuelve init_point
  GET  /billing/me             → estado actual de la suscripción
  POST /billing/me/cancel      → cancela en MP y marca CANCELED
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_business
from app.models.business import Business
from app.models.subscription import Subscription
from app.services import subscription as sub_svc
from app.services.mercadopago import MercadoPagoError

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


class CheckoutRequest(BaseModel):
    payer_email: EmailStr


class SubscriptionOut(BaseModel):
    id: UUID
    status: str
    plan_name: str
    price_usd: float
    currency: str
    trial_ends_at: Optional[datetime]
    current_period_end: Optional[datetime]
    canceled_at: Optional[datetime]
    granted_free_months: int
    mp_init_point: Optional[str]
    has_access: bool

    @classmethod
    def from_model(cls, s: Subscription) -> "SubscriptionOut":
        return cls(
            id=s.id,
            status=s.status.value if hasattr(s.status, "value") else str(s.status),
            plan_name=s.plan_name,
            price_usd=float(s.price_usd),
            currency=s.currency,
            trial_ends_at=s.trial_ends_at,
            current_period_end=s.current_period_end,
            canceled_at=s.canceled_at,
            granted_free_months=s.granted_free_months,
            mp_init_point=s.mp_init_point,
            has_access=s.has_access,
        )


@router.get("/me", response_model=SubscriptionOut)
async def get_my_subscription(
    biz: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sub = await sub_svc.get_or_create_subscription(db, biz)
    return SubscriptionOut.from_model(sub)


@router.post("/me/checkout", response_model=SubscriptionOut)
async def start_checkout(
    payload: CheckoutRequest,
    biz: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    try:
        sub = await sub_svc.start_checkout(db, biz, payer_email=str(payload.payer_email))
    except MercadoPagoError as exc:
        raise HTTPException(status_code=502, detail=f"MercadoPago error: {exc}")
    return SubscriptionOut.from_model(sub)


@router.post("/me/cancel", response_model=SubscriptionOut)
async def cancel_my_subscription(
    biz: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.business_id == biz.id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Sin suscripción activa")
    sub = await sub_svc.cancel(db, sub)
    return SubscriptionOut.from_model(sub)


@router.get("/pricing")
async def get_pricing():
    return {
        "plan_name": settings.SAAS_PLAN_NAME,
        "price_usd": settings.SAAS_PRICE_USD,
        "currency": settings.SAAS_CURRENCY,
        "trial_days": settings.SAAS_TRIAL_DAYS,
    }
