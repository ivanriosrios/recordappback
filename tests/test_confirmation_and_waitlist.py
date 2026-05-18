"""
Tests del flujo anti no-show: confirmación obligatoria 2h antes y
sustitución automática vía waitlist. Ambos handlers viven en
inbound_router y son críticos para el wedge del producto.
"""
import uuid
from datetime import date, datetime, timedelta

import pytest

from tests.conftest import make_business, make_client

from app.services import inbound_router
from app.services.inbound_router import (
    _handle_awaiting_confirmation,
    _handle_waitlist_offer,
)


@pytest.fixture
def dedicated(monkeypatch):
    """Asegura modo dedicado para evitar lookups por número shared."""
    monkeypatch.setattr(inbound_router.settings, "SHARED_WHATSAPP_MODE", False)


def _make_service(session, business_id):
    from app.models.service import Service
    s = Service(
        id=uuid.uuid4(),
        business_id=business_id,
        name="Corte",
        is_active=True,
    )
    session.add(s)
    session.flush()
    return s


def _make_appt(session, biz, client, service, status):
    from app.models.appointment import Appointment, AppointmentStatus
    appt = Appointment(
        id=uuid.uuid4(),
        business_id=biz.id,
        client_id=client.id,
        service_id=service.id,
        status=status,
        appointment_date=date.today() + timedelta(days=1),
        appointment_time="14:00",
    )
    session.add(appt)
    session.flush()
    return appt


# ── Confirmación ──────────────────────────────────────────────────────

def test_confirm_yes_moves_to_confirmed(db_session, fake_provider, dedicated):
    from app.models.appointment import AppointmentStatus
    biz = make_business(db_session)
    client = make_client(db_session, biz.id)
    svc = _make_service(db_session, biz.id)
    appt = _make_appt(db_session, biz, client, svc, AppointmentStatus.AWAITING_CONFIRMATION)
    appt.confirmation_requested_at = datetime.utcnow()
    db_session.commit()

    handled = _handle_awaiting_confirmation(db_session, biz, client, "sí")
    db_session.commit()

    assert handled is True
    assert appt.status == AppointmentStatus.CONFIRMED
    assert appt.confirmed_by_client_at is not None
    assert any("Te esperamos" in m["body"] for m in fake_provider)


def test_confirm_no_cancels(db_session, fake_provider, dedicated, monkeypatch):
    from app.models.appointment import AppointmentStatus
    biz = make_business(db_session)
    client = make_client(db_session, biz.id)
    svc = _make_service(db_session, biz.id)
    appt = _make_appt(db_session, biz, client, svc, AppointmentStatus.AWAITING_CONFIRMATION)
    appt.confirmation_requested_at = datetime.utcnow()
    db_session.commit()

    # Evitar que el task de waitlist intente conectar a Redis en tests
    monkeypatch.setattr(
        "app.tasks.waitlist_matching.process_waitlist_for_appointment_task.delay",
        lambda *a, **k: None,
    )
    handled = _handle_awaiting_confirmation(db_session, biz, client, "no")
    db_session.commit()

    assert handled is True
    assert appt.status == AppointmentStatus.CANCELLED


def test_confirm_no_appointment_returns_false(db_session, fake_provider, dedicated):
    biz = make_business(db_session)
    client = make_client(db_session, biz.id)
    db_session.commit()
    assert _handle_awaiting_confirmation(db_session, biz, client, "sí") is False


# ── Waitlist ──────────────────────────────────────────────────────────

def _make_waitlist_offer(session, biz, client, service, appt):
    from app.models.waitlist import WaitlistEntry, WaitlistStatus
    entry = WaitlistEntry(
        id=uuid.uuid4(),
        business_id=biz.id,
        client_id=client.id,
        service_id=service.id,
        status=WaitlistStatus.OFFERED,
        offered_appointment_id=appt.id,
        offered_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=60),
    )
    session.add(entry)
    session.flush()
    return entry


def test_waitlist_yes_creates_appointment(db_session, fake_provider, dedicated):
    from app.models.appointment import AppointmentStatus, Appointment
    from app.models.waitlist import WaitlistStatus
    biz = make_business(db_session)
    src_client = make_client(db_session, biz.id, phone="+573000000001", name="src")
    new_client = make_client(db_session, biz.id, phone="+573000000002", name="nuevo")
    svc = _make_service(db_session, biz.id)
    src_appt = _make_appt(db_session, biz, src_client, svc, AppointmentStatus.CANCELLED)
    entry = _make_waitlist_offer(db_session, biz, new_client, svc, src_appt)
    db_session.commit()

    handled = _handle_waitlist_offer(db_session, biz, new_client, "si lo tomo")
    db_session.commit()

    assert handled is True
    assert entry.status == WaitlistStatus.ACCEPTED
    rescued = (
        db_session.query(Appointment)
        .filter(Appointment.client_id == new_client.id)
        .filter(Appointment.rescued_from_waitlist.is_(True))
        .all()
    )
    assert len(rescued) == 1
    assert rescued[0].status == AppointmentStatus.CONFIRMED


def test_waitlist_no_declines_and_continues(db_session, fake_provider, dedicated, monkeypatch):
    from app.models.appointment import AppointmentStatus
    from app.models.waitlist import WaitlistStatus
    biz = make_business(db_session)
    src_client = make_client(db_session, biz.id, phone="+573000000003", name="src2")
    new_client = make_client(db_session, biz.id, phone="+573000000004", name="nuevo2")
    svc = _make_service(db_session, biz.id)
    src_appt = _make_appt(db_session, biz, src_client, svc, AppointmentStatus.CANCELLED)
    entry = _make_waitlist_offer(db_session, biz, new_client, svc, src_appt)
    db_session.commit()

    monkeypatch.setattr(
        "app.tasks.waitlist_matching.process_waitlist_for_appointment_task.delay",
        lambda *a, **k: None,
    )
    handled = _handle_waitlist_offer(db_session, biz, new_client, "no, otro día")
    db_session.commit()

    assert handled is True
    assert entry.status == WaitlistStatus.DECLINED


def test_waitlist_expired_offer_is_skipped(db_session, fake_provider, dedicated):
    from app.models.appointment import AppointmentStatus
    from app.models.waitlist import WaitlistEntry, WaitlistStatus
    biz = make_business(db_session)
    client = make_client(db_session, biz.id)
    svc = _make_service(db_session, biz.id)
    src_appt = _make_appt(db_session, biz, client, svc, AppointmentStatus.CANCELLED)
    entry = WaitlistEntry(
        id=uuid.uuid4(),
        business_id=biz.id,
        client_id=client.id,
        service_id=svc.id,
        status=WaitlistStatus.OFFERED,
        offered_appointment_id=src_appt.id,
        offered_at=datetime.utcnow() - timedelta(hours=2),
        expires_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db_session.add(entry)
    db_session.commit()

    # Ya expiró → el handler la marca EXPIRED y devuelve False (no procesa SI/NO)
    handled = _handle_waitlist_offer(db_session, biz, client, "si")
    db_session.commit()
    assert handled is False
    assert entry.status == WaitlistStatus.EXPIRED
