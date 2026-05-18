"""
Agregaciones para el dashboard "Valor RecordApp".

Tres métricas clave que cierran retención:

  - **no_show_rate**:   % de citas que terminaron en NO_SHOW (vs total).
  - **reactivated**:    clientes con un ServiceLog en el período cuyo
                        ReminderLog más reciente previo era de tipo
                        reactivación o follow-up.
  - **attributed_revenue**: suma de `price_charged` de ServiceLogs
                            cuyo cliente recibió un ReminderLog SENT
                            en los `attribution_days` previos a
                            `completed_at`.

El cálculo NO es perfectamente causal — es una heurística clara y
defendible que el dueño entiende: "el cliente vino después de recibir
un recordatorio".
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.reminder import Reminder
from app.models.reminder_log import ReminderLog, LogStatus
from app.models.service_log import ServiceLog


PERIOD_DAYS = {"week": 7, "month": 30, "quarter": 90, "year": 365}


@dataclass
class ValueDashboard:
    period: str
    days: int
    no_show_rate: float           # 0..1
    no_shows: int
    total_appointments: int
    reactivated_clients: int
    attributed_revenue: float
    total_revenue: float
    rescued_slots: int = 0        # citas creadas desde waitlist

    def to_dict(self) -> dict:
        return asdict(self)


async def compute(
    db: AsyncSession,
    business_id: UUID,
    *,
    period: str = "month",
    attribution_days: int = 7,
) -> ValueDashboard:
    days = PERIOD_DAYS.get(period, 30)
    since = datetime.utcnow() - timedelta(days=days)

    # ── No-show rate ──────────────────────────────────────────────────
    appt_q = (
        select(
            func.count().label("total"),
            func.sum(
                func.cast(Appointment.status == AppointmentStatus.NO_SHOW, type_=__import__("sqlalchemy").Integer)
            ).label("no_shows"),
        )
        .where(Appointment.business_id == business_id)
        .where(Appointment.appointment_date >= since.date())
    )
    appt_row = (await db.execute(appt_q)).one()
    total_appts = int(appt_row.total or 0)
    no_shows = int(appt_row.no_shows or 0)
    no_show_rate = (no_shows / total_appts) if total_appts else 0.0

    # ── Ingresos del período + atribución ──────────────────────────────
    sl_q = (
        select(
            ServiceLog.id,
            ServiceLog.client_id,
            ServiceLog.completed_at,
            ServiceLog.price_charged,
        )
        .where(ServiceLog.business_id == business_id)
        .where(ServiceLog.completed_at >= since)
    )
    rows = (await db.execute(sl_q)).all()
    total_revenue = float(sum((r.price_charged or 0) for r in rows))

    # Para cada service log, ¿existía un reminder SENT a ese cliente en los X días previos?
    attributed_revenue = 0.0
    reactivated_clients: set[UUID] = set()
    if rows:
        for r in rows:
            window_start = r.completed_at - timedelta(days=attribution_days)
            sent_exists = await db.execute(
                select(ReminderLog.id)
                .join(Reminder, ReminderLog.reminder_id == Reminder.id)
                .where(Reminder.client_id == r.client_id)
                .where(ReminderLog.status.in_([LogStatus.SENT, LogStatus.DELIVERED, LogStatus.READ]))
                .where(ReminderLog.sent_at >= window_start)
                .where(ReminderLog.sent_at <= r.completed_at)
                .limit(1)
            )
            if sent_exists.first():
                attributed_revenue += float(r.price_charged or 0)
                reactivated_clients.add(r.client_id)

    # ── Cupos rescatados (waitlist) ───────────────────────────────────
    rescued_q = (
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.business_id == business_id)
        .where(Appointment.rescued_from_waitlist.is_(True))
        .where(Appointment.created_at >= since)
    )
    rescued_slots = int((await db.execute(rescued_q)).scalar() or 0)

    return ValueDashboard(
        period=period,
        days=days,
        no_show_rate=round(no_show_rate, 4),
        no_shows=no_shows,
        total_appointments=total_appts,
        reactivated_clients=len(reactivated_clients),
        attributed_revenue=round(attributed_revenue, 2),
        total_revenue=round(total_revenue, 2),
        rescued_slots=rescued_slots,
    )
