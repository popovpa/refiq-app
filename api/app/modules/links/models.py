from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import LinkStatus as TrackingLinkStatus
from app.core.database import Base
from app.core.ids import fk_column, pk_column
from app.modules.campaigns.models import Campaign  # noqa: F401


class TrackingLink(Base):
    __tablename__ = "tracking_links"

    id: Mapped[int] = pk_column()
    short_code: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)
    offer_id: Mapped[int] = fk_column("offers.id")
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
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


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = pk_column()
    tracking_link_id: Mapped[int] = fk_column("tracking_links.id")
    rqcid: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    referer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
