from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    offer_id: Mapped[int] = fk_column("offers.id")
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    tracking_link_id: Mapped[int | None] = fk_column("tracking_links.id", nullable=True)
    partner_tracking_link_id: Mapped[int | None] = fk_column("tracking_links.id", nullable=True)
    click_id: Mapped[str | None] = mapped_column(String(100), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    commission_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
