"""
API de Citas (Appointments) — KOS-51.

Permite al negocio gestionar las citas solicitadas vía chatbot:
- Listar citas (filtrar por estado, fecha)
- Ver detalle de una cita
- Confirmar / rechazar / completar una cita

No expone creación manual (las citas se crean por chatbot).
"""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.schemas.appointment import AppointmentListItem, AppointmentResponse, AppointmentUpdate

router = APIRouter(prefix="/businesses/{business_id}/appointments", tags=["appointments"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_appointment_or_404(
    db: AsyncSession, business_id: UUID, appointment_id: UUID
) -> Appointment:
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return appt


async def _enrich_list_item(db: AsyncSession, appt: Appointment) -> AppointmentListItem:
    """Agrega client_name y service_name al item de lista."""
    client_name = None
    service_name = None

    if appt.client_id:
        res = await db.execute(select(Client).where(Client.id == appt.client_id))
        client = res.scalar_one_or_none()
        if client:
            client_name = client.display_name

    if appt.service_id:
        res = await db.execute(select(Service).where(Service.id == appt.service_id))
        service = res.scalar_one_or_none()
        if service:
            service_name = service.name

    return AppointmentListItem(
        id=appt.id,
        client_id=appt.client_id,
        client_name=client_name,
        service_id=appt.service_id,
        service_name=service_name,
        status=appt.status,
        appointment_date=appt.appointment_date,
        appointment_time=appt.appointment_time,
        shift=appt.shift,
        confirmed_at=appt.confirmed_at,
        created_at=appt.created_at,
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[AppointmentListItem])
async def list_appointments(
    business_id: UUID,
    appt_status: AppointmentStatus | None = Query(None, alias="status"),
    from_date: date | None = Query(None, description="Filtrar desde esta fecha (inclusive)"),
    to_date: date | None = Query(None, description="Filtrar hasta esta fecha (inclusive)"),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Lista citas del negocio con filtros opcionales de estado y rango de fechas."""
    q = select(Appointment).where(Appointment.business_id == business_id)

    if appt_status:
        q = q.where(Appointment.status == appt_status)
    if from_date:
        q = q.where(Appointment.appointment_date >= from_date)
    if to_date:
        q = q.where(Appointment.appointment_date <= to_date)

    q = q.order_by(Appointment.appointment_date, Appointment.appointment_time)

    result = await db.execute(q)
    appointments = result.scalars().all()

    items = []
    for appt in appointments:
        items.append(await _enrich_list_item(db, appt))
    return items


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el detalle completo de una cita."""
    return await _get_appointment_or_404(db, business_id, appointment_id)


@router.post("/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirma una cita solicitada.
    Notifica al cliente vía WhatsApp con la confirmación.
    """
    appt = await _get_appointment_or_404(db, business_id, appointment_id)

    if appt.status != AppointmentStatus.REQUESTED:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden confirmar citas en estado 'requested'. Estado actual: {appt.status}"
        )

    appt.status = AppointmentStatus.CONFIRMED
    appt.confirmed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(appt)

    # Notificar al cliente vía WhatsApp
    await _notify_client_appointment(db, appt, action="confirmed")

    return appt


@router.post("/{appointment_id}/reject", response_model=AppointmentResponse)
async def reject_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Rechaza una cita solicitada.
    Notifica al cliente que la cita no fue aceptada.
    """
    appt = await _get_appointment_or_404(db, business_id, appointment_id)

    if appt.status not in (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede rechazar una cita en estado '{appt.status}'"
        )

    appt.status = AppointmentStatus.REJECTED
    await db.flush()
    await db.refresh(appt)

    await _notify_client_appointment(db, appt, action="rejected")

    return appt


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
async def complete_appointment(
    business_id: UUID,
    appointment_id: UUID,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Marca una cita confirmada como completada (el servicio fue realizado)."""
    appt = await _get_appointment_or_404(db, business_id, appointment_id)

    if appt.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden completar citas confirmadas. Estado actual: {appt.status}"
        )

    appt.status = AppointmentStatus.COMPLETED
    appt.completed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(appt)

    return appt


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    business_id: UUID,
    appointment_id: UUID,
    data: AppointmentUpdate,
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza campos de una cita (hora, turno, o estado)."""
    appt = await _get_appointment_or_404(db, business_id, appointment_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(appt, field, value)

    await db.flush()
    await db.refresh(appt)
    return appt


# ─── Helper de notificación ───────────────────────────────────────────────────

async def _notify_client_appointment(
    db: AsyncSession,
    appt: Appointment,
    action: str,  # "confirmed" | "rejected"
) -> None:
    """Envía WhatsApp al cliente informando la confirmación o rechazo de su cita."""
    from app.chatbot.flows.booking import DAY_NAMES, MONTH_NAMES, _format_time_display
    from app.chatbot import messages as MSG
    from app.messaging import get_messaging_provider

    try:
        res = await db.execute(select(Client).where(Client.id == appt.client_id))
        client = res.scalar_one_or_none()
        if not client:
            return

        res = await db.execute(select(Business).where(Business.id == appt.business_id))
        business = res.scalar_one_or_none()
        business_name = business.name if business else "el negocio"

        service_name = "—"
        if appt.service_id:
            res = await db.execute(select(Service).where(Service.id == appt.service_id))
            svc = res.scalar_one_or_none()
            if svc:
                service_name = svc.name

        day_name = DAY_NAMES[appt.appointment_date.weekday()]
        month = MONTH_NAMES[appt.appointment_date.month]
        date_str = f"{day_name} {appt.appointment_date.day} {month}"

        # Formatear hora/turno
        from app.models.appointment import AppointmentShift
        from app.chatbot.flows.booking import SHIFT_LABELS
        if appt.appointment_time:
            time_str = str(appt.appointment_time)[:5]
        elif appt.shift:
            time_str = SHIFT_LABELS.get(appt.shift, str(appt.shift))
        else:
            time_str = "—"

        provider = get_messaging_provider()

        if action == "confirmed":
            msg = MSG.APPOINTMENT_CONFIRMED_CLIENT.format(
                service=service_name,
                date=date_str,
                time=time_str,
                business=business_name,
            )
        else:
            msg = MSG.APPOINTMENT_REJECTED_CLIENT.format(date=date_str)

        provider.send_text(to=client.phone, body=msg)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[appointments] Error notificando cliente: {e}")
