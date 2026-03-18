import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ConversationStep(str, enum.Enum):
    IDLE = "idle"
    SELECTING_SERVICE = "selecting_service"
    SELECTING_DATE = "selecting_date"
    SELECTING_SLOT = "selecting_slot"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, unique=True
    )
    step: Mapped[ConversationStep] = mapped_column(
        SAEnum(ConversationStep, name="conversationstep", create_type=False),
        nullable=False,
        default=ConversationStep.IDLE,
    )
    context_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    business: Mapped["Business"] = relationship("Business")
    client: Mapped["Client"] = relationship("Client")

    def __repr__(self) -> str:
        return f"<ConversationState client={self.client_id} step={self.step}>"
