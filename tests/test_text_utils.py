from app.core.text import normalize, phone_suffix, strip_whatsapp_prefix


def test_normalize_lowercases_and_strips_accents():
    assert normalize("Sí, Está") == "si, esta"


def test_normalize_handles_empty():
    assert normalize("") == ""
    assert normalize(None) == ""  # type: ignore[arg-type]


def test_phone_suffix_strips_non_digits():
    assert phone_suffix("whatsapp:+57 300 123 4567") == "3001234567"


def test_phone_suffix_returns_empty_when_no_digits():
    assert phone_suffix("abc") == ""


def test_strip_whatsapp_prefix():
    assert strip_whatsapp_prefix("whatsapp:+573001234567") == "+573001234567"
    assert strip_whatsapp_prefix("") == ""
