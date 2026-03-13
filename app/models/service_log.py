import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ServiceLog(Base):
    __tablename__ = "service_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # rating: 1-5, None si aún no ha respondido
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="service_logs")
    client: Mapped["Client"] = relationship("Client", back_populates="service_logs")
    service: Mapped["Service"] = relationship("Service", back_populates="service_logs")

    def __repr__(self) -> str:
        return f"<ServiceLog client={self.client_id} service={self.service_id} rating={self.rating}>"
