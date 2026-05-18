"""
Fixtures de pytest para tests rápidos.

Usa SQLite en memoria + StaticPool. Cubre el modelo de dominio sin
necesidad de levantar Postgres ni Redis. Para tipos PostgreSQL específicos
(UUID, ENUM), se hace un fallback a String en SQLite.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Compatibilidad SQLite ↔ tipos PostgreSQL-only:
# permite que `Base.metadata.create_all()` no explote en tests offline.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "CHAR(36)"

# Asegura imports `app.*` con cwd arbitrario
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Configuración mínima antes de importar la app.
# Usamos un URL postgres dummy — la app crea un engine global perezoso
# que NO conecta hasta el primer query. En estos tests usamos un engine
# SQLite local creado en el fixture `db_session`.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("MESSAGING_PROVIDER", "twilio")
os.environ.setdefault("ENV", "test")


@pytest.fixture
def db_session(monkeypatch):
    # Importar tarde para que las env vars apliquen
    from app.core.database import Base
    import app.models  # noqa: F401 — registra todos los modelos en metadata

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def fake_provider(monkeypatch):
    """Captura los mensajes enviados por el chatbot, sin tocar Twilio."""
    sent: list[dict] = []

    class _FakeProvider:
        def send_text(self, to: str, body: str):
            sent.append({"to": to, "body": body})
            class _R:
                success = True
                message_id = "fake-sid"
                error = ""
            return _R()

        def send_template(self, **kwargs):
            sent.append({"template": kwargs})
            class _R:
                success = True
                message_id = "fake-sid"
                error = ""
            return _R()

    monkeypatch.setattr(
        "app.messaging.factory.get_messaging_provider",
        lambda: _FakeProvider(),
        raising=True,
    )
    monkeypatch.setattr(
        "app.messaging.get_messaging_provider",
        lambda: _FakeProvider(),
        raising=True,
    )
    return sent


def make_business(session, *, phone="+14155238886", name="BizTest"):
    from app.models.business import Business, PlanType
    biz = Business(
        id=uuid.uuid4(),
        name=name,
        business_type="general",
        whatsapp_phone=phone,
        plan=PlanType.FREE,
    )
    session.add(biz)
    session.flush()
    return biz


def make_client(session, business_id, *, phone="+573001234567", name="Ana"):
    from app.models.client import Client, ClientStatus, ChannelType
    c = Client(
        id=uuid.uuid4(),
        business_id=business_id,
        display_name=name,
        phone=phone,
        preferred_channel=ChannelType.WHATSAPP,
        status=ClientStatus.ACTIVE,
    )
    session.add(c)
    session.flush()
    return c
