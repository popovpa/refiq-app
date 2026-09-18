from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class BusinessSubscription(Base):
    __tablename__ = "business_subscriptions"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    plan: Mapped[str] = mapped_column(String(50), default="pro")
    plan_id: Mapped[int | None] = fk_column("plans.id", nullable=True)
    plan_version_id: Mapped[int | None] = fk_column("plan_versions.id", nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="trial")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlatformFee(Base):
    __tablename__ = "platform_fees"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    invoice_id: Mapped[int | None] = fk_column("billing_invoices.id", nullable=True)
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingTransaction(Base):
    __tablename__ = "billing_transactions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_billing_transactions_idempotency"),)

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    invoice_id: Mapped[int | None] = fk_column("billing_invoices.id", nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default="created")
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_status: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str | None] = mapped_column(String(191))
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(50))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
