"""
Tests del orquestador inbound_router — verifica multi-tenancy estricto
y el flujo de routing por contexto.
"""
import pytest
from tests.conftest import make_business, make_client

from app.core.config import get_settings
from app.services import inbound_router
from app.services.inbound_router import resolve_business, find_client


@pytest.fixture
def dedicated_mode(monkeypatch):
    """Forzar modo dedicado (no shared) para los tests legacy."""
    monkeypatch.setattr(inbound_router.settings, "SHARED_WHATSAPP_MODE", False)


@pytest.fixture
def shared_mode(monkeypatch):
    monkeypatch.setattr(inbound_router.settings, "SHARED_WHATSAPP_MODE", True)


# ── Modo dedicado ──────────────────────────────────────────────────────

def test_resolve_business_by_to_number(db_session, dedicated_mode):
    biz = make_business(db_session, phone="+14155238886")
    db_session.commit()
    assert resolve_business(db_session, "whatsapp:+14155238886").id == biz.id


def test_resolve_business_ignores_soft_deleted(db_session, dedicated_mode):
    from datetime import datetime
    biz = make_business(db_session, phone="+14155238886")
    biz.deleted_at = datetime.utcnow()
    db_session.commit()
    assert resolve_business(db_session, "whatsapp:+14155238886") is None


def test_resolve_business_returns_none_for_unknown(db_session, dedicated_mode):
    assert resolve_business(db_session, "whatsapp:+19998887777") is None


# ── Modo compartido (SHARED_WHATSAPP_MODE=True) ────────────────────────

def test_shared_resolve_by_client_phone(db_session, shared_mode):
    biz = make_business(db_session, phone="+14155238886")
    make_client(db_session, biz.id, phone="+573001234567")
    db_session.commit()
    found = resolve_business(
        db_session,
        "whatsapp:+14155238886",
        from_number="whatsapp:+573001234567",
    )
    assert found.id == biz.id


def test_shared_resolve_returns_none_for_unknown_client(db_session, shared_mode):
    make_business(db_session, phone="+14155238886")
    db_session.commit()
    found = resolve_business(
        db_session,
        "whatsapp:+14155238886",
        from_number="whatsapp:+573009999999",
    )
    assert found is None


# ── Scope multi-tenant del cliente ─────────────────────────────────────

def test_find_client_is_scoped_by_business(db_session):
    biz_a = make_business(db_session, phone="+14155238886", name="A")
    biz_b = make_business(db_session, phone="+14155238887", name="B")
    client_a = make_client(db_session, biz_a.id, phone="+573001234567", name="Ana_A")
    client_b = make_client(db_session, biz_b.id, phone="+573001234567", name="Ana_B")
    db_session.commit()

    found_a = find_client(db_session, biz_a.id, "whatsapp:+573001234567")
    found_b = find_client(db_session, biz_b.id, "whatsapp:+573001234567")
    assert found_a.id == client_a.id
    assert found_b.id == client_b.id
    assert found_a.id != found_b.id


def test_find_client_skips_soft_deleted(db_session):
    from datetime import datetime
    biz = make_business(db_session)
    c = make_client(db_session, biz.id, phone="+573001234567")
    c.deleted_at = datetime.utcnow()
    db_session.commit()
    assert find_client(db_session, biz.id, "whatsapp:+573001234567") is None
