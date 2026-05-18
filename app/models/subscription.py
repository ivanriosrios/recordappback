"""
Subscription — suscripción SaaS del negocio a RecordApp.

Estados:
  trialing  → en período de prueba con tarjeta capturada
  active    → cobro recurrente exitoso
  past_due  → último cobro falló; aún con acceso temporal
  canceled  → suspendido, sin acceso
  free      → cortesía otorgada por admin (no cobra)

Una suscripción por negocio. El cobro se maneja con MercadoPago
(preapproval = autorización recurrente).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, Numeric, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    FREE = "free"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("uq_subscriptions_business", "business_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscriptionstatus",
               values_callable=lambda e: [x.value for x in e],
               create_type=True),
        default=SubscriptionStatus.TRIALING,
        nullable=False,
    )
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Pro")
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=12.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Cortesías otorgadas por el admin (cada una extiende current_period_end +1 mes)
    granted_free_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Identificadores en MercadoPago
    mp_preapproval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mp_payer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    mp_init_point: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    business: Mapped["Business"] = relationship("Business")
    payments: Mapped[list["SaasPayment"]] = relationship(
        "SaasPayment", back_populates="subscription", cascade="all, delete-orphan"
    )

    @property
    def has_access(self) -> bool:
        """¿El negocio tiene acceso activo hoy?"""
        now = datetime.utcnow()
        if self.status == SubscriptionStatus.CANCELED:
            return False
        if self.status == SubscriptionStatus.TRIALING:
            return self.trial_ends_at is None or self.trial_ends_at > now
        if self.status == SubscriptionStatus.FREE:
            return self.current_period_end is None or self.current_period_end > now
        if self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
            return self.current_period_end is None or self.current_period_end > now
        return False

    def __repr__(self) -> str:
        return f"<Subscription biz={self.business_id} status={self.status}>"


class SaasPayment(Base):
    """Cada intento de cobro registrado por webhook de MercadoPago."""
    __tablename__ = "saas_payments"
    __table_args__ = (
        Index("ix_saas_payments_subscription", "subscription_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mp_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # approved/rejected/pending/...
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="payments")
