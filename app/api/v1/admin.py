"""
Endpoints de administración interna de OlaApp.
Protegidos por X-Admin-Key header — solo para uso del equipo OlaApp.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import require_super_admin
from app.core.config import get_settings
from app.models.business import Business, WhatsAppStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.business import BusinessResponse
from app.services import subscription as sub_svc

_settings = get_settings()

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def verify_admin_key(x_admin_key: str = Header(...)):
    if not ADMIN_SECRET:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET no configurado en el servidor")
    if x_admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Clave de administrador inválida")


class WhatsAppStatusUpdate(BaseModel):
    status: WhatsAppStatus


# ── Listar todos los negocios ─────────────────────────────────────────────────

@router.get("/businesses", response_model=list[BusinessResponse])
async def list_all_businesses(
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos los negocios registrados con su estado de WhatsApp."""
    result = await db.execute(
        select(Business).order_by(Business.created_at.desc())
    )
    return result.scalars().all()


# ── Cambiar estado de WhatsApp de un negocio ─────────────────────────────────

@router.patch("/businesses/{business_id}/whatsapp-status", response_model=BusinessResponse)
async def set_whatsapp_status(
    business_id: UUID,
    data: WhatsAppStatusUpdate,
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza el estado de WhatsApp de un negocio.

    Estados válidos:
    - not_configured: recién registrado, pendiente de configurar
    - pending: número enviado a Meta, esperando aprobación
    - active: Meta aprobó, mensajes activos

    Uso desde terminal:
    curl -X PATCH https://tu-backend.railway.app/api/v1/admin/businesses/{id}/whatsapp-status \\
         -H "X-Admin-Key: TU_ADMIN_SECRET" \\
         -H "Content-Type: application/json" \\
         -d '{"status": "active"}'
    """
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    business.whatsapp_status = data.status
    await db.flush()
    await db.refresh(business)
    return business


# ── Activar WhatsApp (shortcut) ───────────────────────────────────────────────

@router.post("/businesses/{business_id}/activate", response_model=BusinessResponse)
async def activate_business_whatsapp(
    business_id: UUID,
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """Activa el WhatsApp de un negocio directamente (Meta aprobó)."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    business.whatsapp_status = WhatsAppStatus.ACTIVE
    await db.flush()
    await db.refresh(business)
    return business


@router.post("/businesses/{business_id}/set-pending", response_model=BusinessResponse)
async def set_business_pending(
    business_id: UUID,
    _: None = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """Marca el número de un negocio como 'enviado a Meta, pendiente de aprobación'."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    business.whatsapp_status = WhatsAppStatus.PENDING
    await db.flush()
    await db.refresh(business)
    return business


# ── Gestión de suscripciones (panel UI super-admin) ───────────────────

class BusinessWithSubscription(BaseModel):
    id: UUID
    name: str
    email: Optional[str]
    whatsapp_phone: str
    whatsapp_status: WhatsAppStatus
    created_at: datetime
    subscription_status: Optional[str]
    plan_name: Optional[str]
    trial_ends_at: Optional[datetime]
    current_period_end: Optional[datetime]
    granted_free_months: int = 0
    has_access: bool = False

    model_config = {"from_attributes": True}


class GrantFreeRequest(BaseModel):
    months: int = 1


def _sync_sub_to_dto(b: Business, s: Optional[Subscription]) -> BusinessWithSubscription:
    return BusinessWithSubscription(
        id=b.id,
        name=b.name,
        email=b.email,
        whatsapp_phone=b.whatsapp_phone,
        whatsapp_status=b.whatsapp_status,
        created_at=b.created_at,
        subscription_status=(s.status.value if s and hasattr(s.status, "value") else (s.status if s else None)),
        plan_name=s.plan_name if s else None,
        trial_ends_at=s.trial_ends_at if s else None,
        current_period_end=s.current_period_end if s else None,
        granted_free_months=s.granted_free_months if s else 0,
        has_access=s.has_access if s else False,
    )


@router.get("/businesses-with-subscription", response_model=list[BusinessWithSubscription])
async def list_businesses_with_subscription(
    _admin: Business = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    biz_rows = (await db.execute(select(Business).order_by(Business.created_at.desc()))).scalars().all()
    subs = (await db.execute(select(Subscription))).scalars().all()
    sub_by_biz = {str(s.business_id): s for s in subs}
    return [_sync_sub_to_dto(b, sub_by_biz.get(str(b.id))) for b in biz_rows]


@router.post("/businesses/{business_id}/grant-free", response_model=BusinessWithSubscription)
async def admin_grant_free(
    business_id: UUID,
    payload: GrantFreeRequest,
    _admin: Business = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    biz = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    sub = await sub_svc.get_or_create_subscription(db, biz)
    months = max(1, payload.months)
    now = datetime.utcnow()
    base = sub.current_period_end or now
    if base < now:
        base = now
    sub.current_period_end = base + timedelta(days=30 * months)
    sub.granted_free_months += months
    if sub.status in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED):
        sub.status = SubscriptionStatus.FREE
        sub.canceled_at = None
    await db.flush()
    await db.refresh(sub)
    return _sync_sub_to_dto(biz, sub)


@router.post("/businesses/{business_id}/reactivate-sub", response_model=BusinessWithSubscription)
async def admin_reactivate_sub(
    business_id: UUID,
    _admin: Business = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    biz = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    sub = await sub_svc.get_or_create_subscription(db, biz)
    if sub.status != SubscriptionStatus.ACTIVE:
        sub.canceled_at = None
        now = datetime.utcnow()
        if sub.granted_free_months > 0 and (sub.current_period_end or now) > now:
            sub.status = SubscriptionStatus.FREE
        else:
            sub.status = SubscriptionStatus.TRIALING
            sub.trial_ends_at = now + timedelta(days=_settings.SAAS_TRIAL_DAYS)
            sub.current_period_end = sub.trial_ends_at
    await db.flush()
    await db.refresh(sub)
    return _sync_sub_to_dto(biz, sub)


@router.post("/businesses/{business_id}/suspend", response_model=BusinessWithSubscription)
async def admin_suspend(
    business_id: UUID,
    _admin: Business = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    biz = (await db.execute(select(Business).where(Business.id == business_id))).scalar_one_or_none()
    if not biz:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    sub = await sub_svc.get_or_create_subscription(db, biz)
    sub.status = SubscriptionStatus.CANCELED
    sub.canceled_at = datetime.utcnow()
    await db.flush()
    await db.refresh(sub)
    return _sync_sub_to_dto(biz, sub)


@router.get("/me/permissions")
async def admin_me_permissions(_admin: Business = Depends(require_super_admin)):
    return {"is_super_admin": True, "email": _admin.email}
