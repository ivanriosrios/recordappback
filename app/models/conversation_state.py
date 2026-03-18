"""
Modelo ConversationState — estado actual de la conversación de chatbot por cliente.

Cada cliente tiene como máximo un ConversationState activo.
El estado expira automáticamente si no hay actividad (limpiado por Celery).
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ConversationStep(str, enum.Enum):
    """Pasos del flujo de agendamiento."""
    IDLE               = "idle"               # Sin conversación activa
    SELECTING_SERVICE  = "selecting_service"  # Esperando que elija servicio
    SELECTING_DATE     = "selecting_date"     # Esperando que elija fecha
    SELECTING_SLOT     = "selecting_slot"     # Esperando que elija hora/turno
    CONFIRMING         = "confirming"         # Esperando confirmación final
    COMPLETED          = "completed"          # Flujo terminado (cita creada)
    CANCELLED          = "cancelled"          # Flujo cancelado


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        unique=True  # Un cliente = un estado activo
    )

    step: Mapped[ConversationStep] = mapped_column(
        SAEnum(ConversationStep, name="conversationstep",
               values_callable=lambda e: [x.value for x in e],
               create_type=False),
        default=ConversationStep.IDLE,
        nullable=False,
    )

    # Datos acumulados durante el flujo (service_id, date, time/shift elegidos)
    context_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Fecha/hora del último mensaje del cliente (para expiración)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business")
    client:   Mapped["Client"]   = relationship("Client",   back_populates="conversation_state")

    def __repr__(self) -> str:
        return f"<ConversationState client={self.client_id} step={self.step}>"
