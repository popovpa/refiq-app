from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = pk_column()
    conversion_id: Mapped[int] = fk_column("conversions.id")
    business_id: Mapped[int] = fk_column("businesses.id")
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
