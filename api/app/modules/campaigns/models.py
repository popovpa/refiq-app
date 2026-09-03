from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import CampaignStatus, CampaignType, PromotionOwner
from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "(partner_id IS NOT NULL AND business_id IS NULL) "
            "OR (partner_id IS NULL AND business_id IS NOT NULL)",
            name="ck_campaigns_single_owner",
        ),
    )

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    campaign_type: Mapped[str] = mapped_column(
        "type",
        String(20),
        default=CampaignType.GENERAL.value,
        server_default=CampaignType.GENERAL.value,
    )
    status: Mapped[str] = mapped_column(String(20), default=CampaignStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def owner_type(self) -> str:
        return PromotionOwner.BUSINESS.value if self.business_id else PromotionOwner.PARTNER.value
