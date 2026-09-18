from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Commission(Base):
    __tablename__ = "commissions"
    __table_args__ = (UniqueConstraint("conversion_id", name="uq_commission_conversion"),)

    id: Mapped[int] = pk_column()
    conversion_id: Mapped[int] = fk_column("conversions.id")
    offer_id: Mapped[int | None] = fk_column("offers.id", nullable=True)
    business_id: Mapped[int] = fk_column("businesses.id")
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    business_legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    partner_legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    commission_type: Mapped[str | None] = mapped_column(String(20))
    commission_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    calculation_base: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    calculation_version: Mapped[str | None] = mapped_column(String(20), default="v1")
    offer_terms_version: Mapped[int | None] = mapped_column(Integer)
    hold_period_days: Mapped[int] = mapped_column(Integer, default=0)
    active_payout_id: Mapped[int | None] = fk_column("payouts.id", nullable=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
