"""
Módulo de reportes de ingresos (KOS-56).

GET /businesses/{id}/reports/income          — resumen del período
GET /businesses/{id}/reports/income/timeline — desglose diario para gráficas
GET /businesses/{id}/reports/income/export   — exportar CSV
"""
import csv
import io
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, cast, func
from sqlalchemy import Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.service import Service
from app.models.service_log import ServiceLog

router = APIRouter(prefix="/businesses/{business_id}/reports", tags=["reports"])
logger = logging.getLogger(__name__)


def _date_range(period: str, date_from: Optional[date], date_to: Optional[date]):
    today = date.today()
    if period == "today":
        return datetime.combine(today, datetime.min.time()), datetime.combine(today, datetime.max.time())
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return datetime.combine(start, datetime.min.time()), datetime.combine(today, datetime.max.time())
    elif period == "month":
        start = today.replace(day=1)
        return datetime.combine(start, datetime.min.time()), datetime.combine(today, datetime.max.time())
    elif period == "year":
        start = today.replace(month=1, day=1)
        return datetime.combine(start, datetime.min.time()), datetime.combine(today, datetime.max.time())
    elif period == "custom" and date_from and date_to:
        return datetime.combine(date_from, datetime.min.time()), datetime.combine(date_to, datetime.max.time())
    else:
        # Default: last 30 days
        start = today - timedelta(days=29)
        return datetime.combine(start, datetime.min.time()), datetime.combine(today, datetime.max.time())


@router.get("/income")
async def get_income_report(
    business_id: UUID,
    period: str = Query("month", enum=["today", "week", "month", "year", "custom"]),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Resumen de ingresos para el período seleccionado."""
    start_dt, end_dt = _date_range(period, date_from, date_to)

    base_filter = and_(
        ServiceLog.business_id == business_id,
        ServiceLog.completed_at >= start_dt,
        ServiceLog.completed_at <= end_dt,
        ServiceLog.price_charged.isnot(None),
    )

    # Totales
    totals_res = await db.execute(
        select(
            func.coalesce(func.sum(ServiceLog.price_charged), 0).label("total_revenue"),
            func.count(ServiceLog.id).label("services_with_price"),
            func.coalesce(func.avg(ServiceLog.price_charged), 0).label("avg_ticket"),
        ).where(base_filter)
    )
    totals = totals_res.one()

    # Total servicios (con y sin precio)
    all_count_res = await db.execute(
        select(func.count(ServiceLog.id)).where(
            and_(
                ServiceLog.business_id == business_id,
                ServiceLog.completed_at >= start_dt,
                ServiceLog.completed_at <= end_dt,
            )
        )
    )
    all_services_count = all_count_res.scalar() or 0

    # Por servicio
    by_service_res = await db.execute(
        select(
            Service.name,
            func.count(ServiceLog.id).label("count"),
            func.coalesce(func.sum(ServiceLog.price_charged), 0).label("revenue"),
        )
        .join(Service, ServiceLog.service_id == Service.id)
        .where(base_filter)
        .group_by(Service.name)
        .order_by(func.sum(ServiceLog.price_charged).desc())
    )
    by_service = [
        {"service_name": row.name, "count": row.count, "revenue": float(row.revenue)}
        for row in by_service_res.all()
    ]

    # Por método de pago
    by_payment_res = await db.execute(
        select(
            ServiceLog.payment_method,
            func.count(ServiceLog.id).label("count"),
            func.coalesce(func.sum(ServiceLog.price_charged), 0).label("revenue"),
        )
        .where(base_filter)
        .group_by(ServiceLog.payment_method)
        .order_by(func.sum(ServiceLog.price_charged).desc())
    )
    by_payment = [
        {
            "method": row.payment_method or "sin_registrar",
            "count": row.count,
            "revenue": float(row.revenue),
        }
        for row in by_payment_res.all()
    ]

    return {
        "period": period,
        "date_from": start_dt.date().isoformat(),
        "date_to": end_dt.date().isoformat(),
        "total_revenue": float(totals.total_revenue),
        "services_with_price": totals.services_with_price,
        "all_services_count": all_services_count,
        "avg_ticket": float(totals.avg_ticket),
        "by_service": by_service,
        "by_payment": by_payment,
    }


@router.get("/income/timeline")
async def get_income_timeline(
    business_id: UUID,
    period: str = Query("month", enum=["week", "month", "year", "custom"]),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Desglose diario de ingresos para gráficas."""
    start_dt, end_dt = _date_range(period, date_from, date_to)

    result = await db.execute(
        select(
            cast(ServiceLog.completed_at, SADate).label("day"),
            func.coalesce(func.sum(ServiceLog.price_charged), 0).label("revenue"),
            func.count(ServiceLog.id).label("count"),
        )
        .where(
            and_(
                ServiceLog.business_id == business_id,
                ServiceLog.completed_at >= start_dt,
                ServiceLog.completed_at <= end_dt,
            )
        )
        .group_by(cast(ServiceLog.completed_at, SADate))
        .order_by(cast(ServiceLog.completed_at, SADate))
    )

    return [
        {"date": str(row.day), "revenue": float(row.revenue), "count": row.count}
        for row in result.all()
    ]


@router.get("/income/export")
async def export_income_csv(
    business_id: UUID,
    period: str = Query("month"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """Exporta registros de ingresos como CSV."""
    start_dt, end_dt = _date_range(period, date_from, date_to)

    result = await db.execute(
        select(ServiceLog, Service.name.label("service_name"))
        .join(Service, ServiceLog.service_id == Service.id)
        .where(
            and_(
                ServiceLog.business_id == business_id,
                ServiceLog.completed_at >= start_dt,
                ServiceLog.completed_at <= end_dt,
            )
        )
        .order_by(ServiceLog.completed_at.desc())
    )
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Servicio", "Precio Cobrado", "Método de Pago", "Notas del Servicio"])

    for row in rows:
        log = row.ServiceLog
        writer.writerow([
            log.completed_at.strftime("%Y-%m-%d %H:%M"),
            row.service_name,
            float(log.price_charged) if log.price_charged is not None else "",
            log.payment_method or "",
            log.service_notes or "",
        ])

    output.seek(0)
    filename = f"ingresos_{start_dt.date()}_{end_dt.date()}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
