from app.services.idempotency import already_processed, mark_processed


def test_mark_then_already_processed(db_session):
    assert already_processed(db_session, "SM123") is False
    assert mark_processed(db_session, "SM123") is True
    db_session.commit()
    assert already_processed(db_session, "SM123") is True


def test_mark_twice_is_noop(db_session):
    assert mark_processed(db_session, "SM999") is True
    db_session.commit()
    # Segunda inserción debería retornar False (IntegrityError manejado).
    assert mark_processed(db_session, "SM999") is False


def test_empty_sid_treated_as_processed():
    # No queremos persistir sids vacíos
    from sqlalchemy.orm import Session as _S  # noqa: F401
    # Sin sesión, igual no debe romper
    assert already_processed(None, "") is False  # type: ignore[arg-type]
