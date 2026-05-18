from app.services import messaging_format
from app.services.messaging_format import prefix_business


def test_prefix_off_returns_body_unchanged(monkeypatch):
    monkeypatch.setattr(messaging_format.settings, "SHARED_WHATSAPP_MODE", False)
    assert prefix_business("Biz", "hola") == "hola"


def test_prefix_on_adds_business_name(monkeypatch):
    monkeypatch.setattr(messaging_format.settings, "SHARED_WHATSAPP_MODE", True)
    assert prefix_business("Biz", "hola").startswith("*Biz*")
    assert "hola" in prefix_business("Biz", "hola")


def test_prefix_skips_when_business_missing(monkeypatch):
    monkeypatch.setattr(messaging_format.settings, "SHARED_WHATSAPP_MODE", True)
    assert prefix_business(None, "hola") == "hola"
    assert prefix_business("", "hola") == "hola"
