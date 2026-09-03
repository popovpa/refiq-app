from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import LinkStatus as TrackingLinkStatus
from app.common.enums import PromotionOwner
from app.core.database import Base
from app.core.ids import fk_column, pk_column
from app.modules.campaigns.models import Campaign  # noqa: F401


class TrackingLink(Base):
    __tablename__ = "tracking_links"
    __table_args__ = (
        CheckConstraint(
            "(partner_id IS NOT NULL AND business_id IS NULL) "
            "OR (partner_id IS NULL AND business_id IS NOT NULL)",
            name="ck_tracking_links_single_owner",
        ),
    )

    id: Mapped[int] = pk_column()
    short_code: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)
    offer_id: Mapped[int] = fk_column("offers.id")
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    campaign_id: Mapped[int | None] = fk_column("campaigns.id", nullable=True)
    destination_url: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    traffic_source: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=TrackingLinkStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def owner_type(self) -> str:
        return PromotionOwner.BUSINESS.value if self.business_id else PromotionOwner.PARTNER.value


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = pk_column()
    tracking_link_id: Mapped[int] = fk_column("tracking_links.id")
    rqcid: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    partner_rqcid: Mapped[str | None] = mapped_column(String(12), index=True)
    client_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    referer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
