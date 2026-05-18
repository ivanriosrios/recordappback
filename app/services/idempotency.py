"""
Dedup de webhooks entrantes por MessageSid.

Uso típico::

    if already_processed(session, sid):
        return
    mark_processed(session, sid, provider="twilio")
    # ... procesar ...
"""
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.processed_message import ProcessedMessage

logger = logging.getLogger(__name__)


def already_processed(session: Session, message_sid: str) -> bool:
    if not message_sid:
        return False
    return session.get(ProcessedMessage, message_sid) is not None


def mark_processed(session: Session, message_sid: str, provider: str = "twilio") -> bool:
    """
    Marca el sid como procesado. Devuelve True si fue insertado,
    False si ya existía (race condition con otro worker).
    """
    if not message_sid:
        return True
    try:
        session.add(ProcessedMessage(message_sid=message_sid, provider=provider))
        session.flush()
        return True
    except IntegrityError:
        session.rollback()
        logger.info(f"[idempotency] sid={message_sid} ya estaba registrado (race)")
        return False
