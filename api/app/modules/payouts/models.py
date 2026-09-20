from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payouts_amount_positive"),
        CheckConstraint("currency = 'RUB'", name="ck_payouts_currency_rub"),
        UniqueConstraint("idempotency_key", name="uq_payouts_idempotency"),
    )

    id: Mapped[int] = pk_column()
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    payout_profile_id: Mapped[int | None] = fk_column("partner_payout_profiles.id", nullable=True)
    payer_business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    payer_legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    recipient_legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="TBANK")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_status: Mapped[str | None] = mapped_column(String(40))
    failure_class: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str | None] = mapped_column(String(191))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["PayoutItem"]] = relationship(back_populates="payout", lazy="selectin")

    @property
    def recipient_partner_id(self) -> int:
        return self.partner_id


class PayoutItem(Base):
    __tablename__ = "payout_items"
    __table_args__ = (UniqueConstraint("payout_id", "commission_id", name="uq_payout_item_commission"),)

    id: Mapped[int] = pk_column()
    payout_id: Mapped[int] = fk_column("payouts.id")
    commission_id: Mapped[int] = fk_column("commissions.id", index=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    excluded_reason: Mapped[str | None] = mapped_column(String(64))

    payout: Mapped["Payout"] = relationship(back_populates="items")
