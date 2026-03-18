"""
Endpoints para gestión de citas (KOS-51).

GET    /businesses/{id}/appointments            — listar citas
GET    /businesses/{id}/appointments/{id}       — detalle
POST   /businesses/{id}/appointments/{id}/confirm  — confirmar
POST   /businesses/{id}/appointments/{id}/reject   — rechazar
POST   /businesses/{id}/appointments/{id}/complete — completar
PATCH  /businesses/{id}/appointments/{id}          — actualizar
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.appointment import Appointment, AppointmentStatus
from app.models.client import Client
from app.models.service import Service

router = APIRouter(prefix="/businesses/{business_id}/appointments", tags=["appointments"])
logger = logging.getLogger(__name__)


def _appt_dict(appt: Appointment, client_name: str | None = None, service_name: str | None = None) -> dict:
    return {
        "id": str(appt.id),
        "business_id": str(appt.business_id),
        "client_id": str(appt.client_id),
        "service_id": str(appt.service_id),
        "client_name": client_name,
        "service_name": service_name,
        "status": appt.status,
        "appointment_date": appt.appointment_date.isoformat() if appt.appointment_date else None,
        "appointment_time": appt.appointment_time,
        "shift": appt.shift,
        "notes": appt.notes,
        "confirmed_at": appt.confirmed_at.isoformat() if appt.confirmed_at else None,
        "completed_at": appt.completed_at.isoformat() if appt.completed_at else None,
        "reminder_sent": appt.reminder_sent,
        "created_at": appt.created_at.isoformat(),
    }


async def _notify_client(client: Client, appt: Appointment, service: Service, action: str):
    """Envía WhatsApp al cliente cuando se confirma o rechaza su cita."""
    try:
        from app.services.whatsapp import whatsapp
        date_str = appt.appointment_date.strftime("%d/%m/%Y")
        time_str = appt.appointment_time or ""
        shift_map = {"morning": "mañana", "afternoon": "tarde", "evening": "noche"}
        shift_str = shift_map.get(str(appt.shift), "")
        when = f"{date_str} {time_str or shift_str}".strip()

        if action == "confirmed":
            text = (
                f"✅ ¡Tu cita ha sido *confirmada*!\n\n"
                f"📋 *Servicio:* {service.name}\n"
                f"📅 *Fecha:* {when}\n\n"
                f"Te esperamos. Si necesitas cancelar, responde *CANCELAR*."
            )
        else:
            text = (
                f"⚠️ Tu solicitud de cita para *{service.name}* el {when} "
                f"no pudo ser confirmada.\n\n"
                f"Por favor contáctanos para reagendar."
            )
        whatsapp.send_text(to=client.phone, body=text)
    except Exception as exc:
        logger.warning(f"[appointments] No se pudo notificar a cliente: {exc}")


@router.get("")
@router.get("/")
async def list_appointments(
    business_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    filters = [Appointment.business_id == business_id]
    if status_filter:
        try:
            filters.append(Appointment.status == AppointmentStatus(status_filter))
        except ValueError:
            pass
    if date_from:
        from datetime import date
        filters.append(Appointment.appointment_date >= date.fromisoformat(date_from))
    if date_to:
        from datetime import date
        filters.append(Appointment.appointment_date <= date.fromisoformat(date_to))

    result = await db.execute(
        select(Appointment).where(and_(*filters)).order_by(
            Appointment.appointment_date.desc(), Appointment.created_at.desc()
        )
    )
    appts = result.scalars().all()

    if not appts:
        return []

    # Batch load clients and services
    client_ids = {a.client_id for a in appts}
    service_ids = {a.service_id for a in appts}

    clients_res = await db.execute(select(Client).where(Client.id.in_(client_ids)))
    clients = {c.id: c.display_name for c in clients_res.scalars().all()}

    services_res = await db.execute(select(Service).where(Service.id.in_(service_ids)))
    services = {s.id: s.name for s in services_res.scalars().all()}

    return [_appt_dict(a, clients.get(a.client_id), services.get(a.service_id)) for a in appts]


@router.get("/{appointment_id}")
async def get_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
    client = client_res.scalar_one_or_none()
    svc_res = await db.execute(select(Service).where(Service.id == appt.service_id))
    service = svc_res.scalar_one_or_none()

    return _appt_dict(
        appt,
        client.display_name if client else None,
        service.name if service else None,
    )


@router.post("/{appointment_id}/confirm")
async def confirm_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if appt.status not in (AppointmentStatus.REQUESTED,):
        raise HTTPException(status_code=400, detail=f"No se puede confirmar una cita en estado {appt.status}")

    appt.status = AppointmentStatus.CONFIRMED
    appt.confirmed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(appt)

    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
    client = client_res.scalar_one_or_none()
    svc_res = await db.execute(select(Service).where(Service.id == appt.service_id))
    service = svc_res.scalar_one_or_none()

    if client and service:
        await _notify_client(client, appt, service, "confirmed")

    return _appt_dict(
        appt,
        client.display_name if client else None,
        service.name if service else None,
    )


@router.post("/{appointment_id}/reject")
async def reject_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    appt.status = AppointmentStatus.REJECTED
    await db.flush()
    await db.refresh(appt)

    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
    client = client_res.scalar_one_or_none()
    svc_res = await db.execute(select(Service).where(Service.id == appt.service_id))
    service = svc_res.scalar_one_or_none()

    if client and service:
        await _notify_client(client, appt, service, "rejected")

    return _appt_dict(
        appt,
        client.display_name if client else None,
        service.name if service else None,
    )


@router.post("/{appointment_id}/complete")
async def complete_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    appt.status = AppointmentStatus.COMPLETED
    appt.completed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(appt)

    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
    client = client_res.scalar_one_or_none()
    svc_res = await db.execute(select(Service).where(Service.id == appt.service_id))
    service = svc_res.scalar_one_or_none()

    return _appt_dict(
        appt,
        client.display_name if client else None,
        service.name if service else None,
    )


@router.patch("/{appointment_id}")
async def update_appointment(
    business_id: UUID,
    appointment_id: UUID,
    data: dict,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    allowed = {"appointment_time", "appointment_date", "shift", "notes", "status"}
    for key, val in data.items():
        if key in allowed and val is not None:
            if key == "status":
                try:
                    val = AppointmentStatus(val)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Estado inválido: {val}")
            setattr(appt, key, val)

    await db.flush()
    await db.refresh(appt)

    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
    client = client_res.scalar_one_or_none()
    svc_res = await db.execute(select(Service).where(Service.id == appt.service_id))
    service = svc_res.scalar_one_or_none()

    return _appt_dict(
        appt,
        client.display_name if client else None,
        service.name if service else None,
    )
