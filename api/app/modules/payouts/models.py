from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = pk_column()
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["PayoutItem"]] = relationship(back_populates="payout", lazy="selectin")


class PayoutItem(Base):
    __tablename__ = "payout_items"

    id: Mapped[int] = pk_column()
    payout_id: Mapped[int] = fk_column("payouts.id")
    commission_id: Mapped[int] = fk_column("commissions.id", index=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    payout: Mapped["Payout"] = relationship(back_populates="items")
