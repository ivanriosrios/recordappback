"""
Tests del orquestador inbound_router — verifica multi-tenancy estricto
y el flujo de routing por contexto.
"""
import pytest
from tests.conftest import make_business, make_client

from app.services.inbound_router import resolve_business, find_client


def test_resolve_business_by_to_number(db_session):
    biz = make_business(db_session, phone="+14155238886")
    db_session.commit()
    assert resolve_business(db_session, "whatsapp:+14155238886").id == biz.id


def test_resolve_business_ignores_soft_deleted(db_session):
    from datetime import datetime
    biz = make_business(db_session, phone="+14155238886")
    biz.deleted_at = datetime.utcnow()
    db_session.commit()
    assert resolve_business(db_session, "whatsapp:+14155238886") is None


def test_resolve_business_returns_none_for_unknown(db_session):
    assert resolve_business(db_session, "whatsapp:+19998887777") is None


def test_find_client_is_scoped_by_business(db_session):
    """
    Bug histórico: dos clientes con el mismo número (en negocios distintos)
    causaban que el mensaje se atribuyera al cliente equivocado.
    """
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
