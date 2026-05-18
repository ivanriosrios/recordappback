"""
Registro de mensajes de webhook ya procesados, para idempotency.

Twilio reintenta webhooks si la respuesta tarda o no es 2xx. Sin dedup
podríamos crear citas duplicadas o registrar calificaciones dos veces.
"""
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    __table_args__ = (
        Index("ix_processed_messages_created_at", "created_at"),
    )

    # MessageSid de Twilio (~34 chars) o ID equivalente del proveedor.
    message_sid: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="twilio")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
