from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import date, timedelta

from app.core.database import get_db
from app.models.reminder import Reminder, ReminderStatus
from app.schemas.reminder import ReminderCreate, ReminderUpdate, ReminderResponse

router = APIRouter(prefix="/businesses/{business_id}/reminders", tags=["reminders"])


@router.post("/", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(business_id: UUID, data: ReminderCreate, db: AsyncSession = Depends(get_db)):
    reminder = Reminder(
        client_id=data.client_id,
        service_id=data.service_id,
        template_id=data.template_id,
        type=data.type,
        recurrence_days=data.recurrence_days,
        next_send_date=data.next_send_date,
        notify_days_before=data.notify_days_before,
    )
    db.add(reminder)
    await db.flush()
    await db.refresh(reminder)
    return reminder


@router.get("/", response_model=list[ReminderResponse])
async def list_reminders(
    business_id: UUID,
    status_filter: ReminderStatus | None = Query(None, alias="status"),
    upcoming_days: int | None = Query(None, ge=1, le=90),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    # Join con Client para filtrar por business_id
    from app.models.client import Client

    query = (
        select(Reminder)
        .join(Client, Reminder.client_id == Client.id)
        .where(Client.business_id == business_id)
    )
    if status_filter:
        query = query.where(Reminder.status == status_filter)
    if upcoming_days:
        deadline = date.today() + timedelta(days=upcoming_days)
        query = query.where(Reminder.next_send_date <= deadline)

    query = query.offset(skip).limit(limit).order_by(Reminder.next_send_date.asc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(business_id: UUID, reminder_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado")
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(business_id: UUID, reminder_id: UUID, data: ReminderUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reminder, field, value)

    await db.flush()
    await db.refresh(reminder)
    return reminder
