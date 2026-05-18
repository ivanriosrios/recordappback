"""
Endpoints para gestionar la lista de espera (waitlist).
"""
from datetime import date as date_cls, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.appointment import AppointmentShift
from app.models.business import Business
from app.models.client import Client
from app.models.waitlist import WaitlistEntry, WaitlistStatus

router = APIRouter(prefix="/businesses/{business_id}/waitlist", tags=["waitlist"])


class WaitlistCreate(BaseModel):
    client_id: UUID
    service_id: UUID
    preferred_date: Optional[date_cls] = None
    preferred_shift: Optional[AppointmentShift] = None


class WaitlistOut(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    service_id: UUID
    client_name: str | None = None
    preferred_date: Optional[date_cls]
    preferred_shift: Optional[AppointmentShift]
    status: WaitlistStatus
    offered_appointment_id: Optional[UUID]
    offered_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


def _entry_to_out(entry: WaitlistEntry, client_name: str | None = None) -> WaitlistOut:
    return WaitlistOut(
        id=entry.id,
        business_id=entry.business_id,
        client_id=entry.client_id,
        service_id=entry.service_id,
        client_name=client_name,
        preferred_date=entry.preferred_date,
        preferred_shift=entry.preferred_shift,
        status=entry.status,
        offered_appointment_id=entry.offered_appointment_id,
        offered_at=entry.offered_at,
        expires_at=entry.expires_at,
        created_at=entry.created_at,
    )


@router.post("/", response_model=WaitlistOut, status_code=status.HTTP_201_CREATED)
async def add_waitlist(
    business_id: UUID,
    data: WaitlistCreate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    client = (await db.execute(
        select(Client).where(Client.id == data.client_id, Client.business_id == business_id)
    )).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    entry = WaitlistEntry(
        business_id=business_id,
        client_id=data.client_id,
        service_id=data.service_id,
        preferred_date=data.preferred_date,
        preferred_shift=data.preferred_shift,
        status=WaitlistStatus.PENDING,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return _entry_to_out(entry, client.display_name)


@router.get("/", response_model=list[WaitlistOut])
async def list_waitlist(
    business_id: UUID,
    status_: WaitlistStatus | None = Query(None, alias="status"),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(WaitlistEntry, Client.display_name)
        .join(Client, Client.id == WaitlistEntry.client_id)
        .where(WaitlistEntry.business_id == business_id)
        .order_by(desc(WaitlistEntry.created_at))
    )
    if status_:
        q = q.where(WaitlistEntry.status == status_)
    rows = (await db.execute(q)).all()
    return [_entry_to_out(e, name) for e, name in rows]


@router.delete("/{entry_id}", status_code=204)
async def remove_waitlist(
    business_id: UUID,
    entry_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    entry = (await db.execute(
        select(WaitlistEntry)
        .where(WaitlistEntry.id == entry_id, WaitlistEntry.business_id == business_id)
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry no encontrada")
    entry.status = WaitlistStatus.REMOVED
    await db.flush()
    return None
