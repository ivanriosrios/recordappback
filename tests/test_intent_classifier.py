from app.services.intent_classifier import classify


def test_optout_keyword():
    assert classify("STOP") == "optout"
    assert classify("Quiero darme de baja") == "optout"


def test_booking_keyword():
    assert classify("Quiero agendar una cita") == "booking_intent"
    assert classify("Tienes turno disponible?") == "booking_intent"


def test_rated_good_keyword():
    assert classify("Excelente servicio") == "rated_good"
    assert classify("Bien") == "rated_good"


def test_rated_bad_keyword():
    assert classify("Pésimo") == "rated_bad"
    assert classify("Mal") == "rated_bad"


def test_yes_no_keywords():
    assert classify("si") == "responded_yes"
    assert classify("no") == "responded_no"


def test_unknown_returns_unknown_without_llm_flag():
    # Sin LLM_INTENT_CLASSIFIER_ENABLED no cae al fallback.
    assert classify("@#$%") == "unknown"
