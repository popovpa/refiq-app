from datetime import datetime
from sqlalchemy import JSON, String, Text, Integer, DateTime, UniqueConstraint, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    product_id: Mapped[int | None] = fk_column("products.id", nullable=True, index=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80))
    category_id: Mapped[int | None] = fk_column("offer_categories.id", nullable=True)
    geo: Mapped[str | None] = mapped_column(String(255))
    hold_period_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    access_policy: Mapped[str] = mapped_column(String(20), default="open")
    conversion_type: Mapped[str] = mapped_column(String(20), default="sale")
    attribution_window_days: Mapped[int] = mapped_column(Integer, default=30)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    allowed_traffic: Mapped[list | None] = mapped_column(JSON)
    forbidden_traffic: Mapped[list | None] = mapped_column(JSON)
    partner_notes: Mapped[str | None] = mapped_column(Text)
    materials: Mapped[list | None] = mapped_column(JSON)
    terms_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    commission_rules: Mapped[list["OfferCommissionRule"]] = relationship(back_populates="offer", lazy="selectin")
    partner_access: Mapped[list["OfferPartnerAccess"]] = relationship(back_populates="offer", lazy="selectin")


class OfferCommissionRule(Base):
    __tablename__ = "offer_commission_rules"

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    offer: Mapped["Offer"] = relationship(back_populates="commission_rules")


class OfferPartnerAccess(Base):
    __tablename__ = "offer_partner_access"

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[str] = mapped_column(String(20), default="marketplace")
    comment: Mapped[str | None] = mapped_column(Text)
    business_comment: Mapped[str | None] = mapped_column(Text)
    traffic_sources: Mapped[list | None] = mapped_column(JSON)
    topics: Mapped[str | None] = mapped_column(String(255))
    geo: Mapped[str | None] = mapped_column(String(255))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    offer_terms_version: Mapped[int | None] = mapped_column(Integer)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    offer: Mapped["Offer"] = relationship(back_populates="partner_access")

    __table_args__ = (
        UniqueConstraint("offer_id", "partner_id", name="uq_offer_partner_access"),
    )
