from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client, ClientStatus, ChannelType
from app.models.service_log import ServiceLog
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/businesses/{business_id}/clients", tags=["clients"])


# ──────────────────────────────────────────────────────────────────────
# Schemas auxiliares
# ──────────────────────────────────────────────────────────────────────

class ClientsPage(BaseModel):
    items: list[ClientResponse]
    total: int
    skip: int
    limit: int


class AtRiskClient(BaseModel):
    id: UUID
    display_name: str
    phone: str
    last_service_at: datetime | None
    days_since: int | None


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    business_id: UUID,
    data: ClientCreate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    if isinstance(data.preferred_channel, ChannelType):
        channel_enum = data.preferred_channel
    elif data.preferred_channel:
        ch_val = str(data.preferred_channel).lower()
        channel_enum = (
            ChannelType(ch_val) if ch_val in {c.value for c in ChannelType} else ChannelType.WHATSAPP
        )
    else:
        channel_enum = ChannelType.WHATSAPP

    client = Client(
        business_id=business_id,
        display_name=data.display_name,
        phone=data.phone,
        email=data.email,
        preferred_channel=channel_enum,
        status=ClientStatus.ACTIVE,
        notes=data.notes,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.get("/", response_model=ClientsPage)
async def list_clients(
    business_id: UUID,
    status: ClientStatus | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    base = (
        select(Client)
        .where(Client.business_id == business_id)
        .where(Client.deleted_at.is_(None))
    )
    if status:
        base = base.where(Client.status == status)
    if search:
        base = base.where(Client.display_name.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    items_q = base.order_by(Client.created_at.desc()).offset(skip).limit(limit)
    items = (await db.execute(items_q)).scalars().all()
    return ClientsPage(items=list(items), total=int(total or 0), skip=skip, limit=limit)


@router.get("/at-risk", response_model=list[AtRiskClient])
async def list_at_risk_clients(
    business_id: UUID,
    days: int = Query(60, ge=7, le=365),
    limit: int = Query(20, ge=1, le=100),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Clientes activos cuyo último ServiceLog es anterior a `days` días
    (o que nunca tuvieron uno). El cliente "en riesgo" se define por
    inactividad real, no por `updated_at` (que cambia con cualquier edit).
    """
    threshold = datetime.utcnow() - timedelta(days=days)
    last_service_subq = (
        select(
            ServiceLog.client_id.label("client_id"),
            func.max(ServiceLog.completed_at).label("last_completed_at"),
        )
        .where(ServiceLog.business_id == business_id)
        .group_by(ServiceLog.client_id)
        .subquery()
    )

    q = (
        select(Client, last_service_subq.c.last_completed_at)
        .outerjoin(last_service_subq, last_service_subq.c.client_id == Client.id)
        .where(Client.business_id == business_id)
        .where(Client.deleted_at.is_(None))
        .where(Client.status == ClientStatus.ACTIVE)
        .where(
            (last_service_subq.c.last_completed_at.is_(None))
            | (last_service_subq.c.last_completed_at < threshold)
        )
        .order_by(
            last_service_subq.c.last_completed_at.asc().nulls_first(),
        )
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    now = datetime.utcnow()
    return [
        AtRiskClient(
            id=client.id,
            display_name=client.display_name,
            phone=client.phone,
            last_service_at=last_at,
            days_since=int((now - last_at).days) if last_at else None,
        )
        for client, last_at in rows
    ]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    business_id: UUID,
    client_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id, Client.business_id == business_id)
        .where(Client.deleted_at.is_(None))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    business_id: UUID,
    client_id: UUID,
    data: ClientUpdate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id, Client.business_id == business_id)
        .where(Client.deleted_at.is_(None))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "preferred_channel" in update_data:
        val = update_data["preferred_channel"]
        if isinstance(val, ChannelType):
            update_data["preferred_channel"] = val
        else:
            ch_val = str(val).lower()
            update_data["preferred_channel"] = (
                ChannelType(ch_val) if ch_val in {c.value for c in ChannelType} else ChannelType.WHATSAPP
            )

    if "status" in update_data:
        val = update_data["status"]
        if isinstance(val, ClientStatus):
            update_data["status"] = val
        else:
            st_val = str(val).lower()
            update_data["status"] = (
                ClientStatus(st_val) if st_val in {s.value for s in ClientStatus} else ClientStatus.ACTIVE
            )

    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_client(
    business_id: UUID,
    client_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete: marca el cliente como eliminado sin perder su historial.
    Los listados estándar lo ocultan; los reportes históricos siguen accesibles.
    """
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id, Client.business_id == business_id)
        .where(Client.deleted_at.is_(None))
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    client.deleted_at = datetime.utcnow()
    await db.flush()
    return None
