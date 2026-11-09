from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import DestinationStatus, DestinationType
from app.core.database import Base
from app.core.ids import fk_column, pk_column


class OfferDestination(Base):
    """Allowed landing page of an offer. Commercial terms stay on Offer."""

    __tablename__ = "offer_destinations"
    __table_args__ = (
        UniqueConstraint("id", "offer_id", name="uq_offer_destinations_id_offer"),
        UniqueConstraint("offer_id", "url", name="uq_offer_destinations_offer_url"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_offer_destinations_status"),
        CheckConstraint("type IN ('PRODUCT', 'CATEGORY', 'LANDING')", name="ck_offer_destinations_type"),
        Index("ix_offer_destinations_offer_status", "offer_id", "status"),
        Index(
            "uq_offer_destinations_one_primary",
            "offer_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default=DestinationType.LANDING.value)
    image_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DestinationStatus.ACTIVE.value)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
