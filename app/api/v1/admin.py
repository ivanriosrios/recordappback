"""
Endpoints de administración interna de OlaApp.
Protegidos por X-Admin-Key header — solo para uso del equipo OlaApp.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models.business import Business, WhatsAppStatus
from app.schemas.business import BusinessResponse

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
