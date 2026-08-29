from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import CreativeSource, CreativeStatus, CreativeType
from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Creative(Base):
    __tablename__ = "creatives"

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    created_by_user_id: Mapped[int] = fk_column("users.id")
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    campaign_id: Mapped[int | None] = fk_column("campaigns.id", nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=CreativeType.TEXT.value)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=CreativeSource.BUSINESS.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CreativeStatus.DRAFT.value, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    text_content: Mapped[dict | None] = mapped_column(JSONB)
    asset_id: Mapped[int | None] = fk_column("assets.id", nullable=True)
    language: Mapped[str | None] = mapped_column(String(8))
    channel: Mapped[str | None] = mapped_column(String(40))
    format: Mapped[str | None] = mapped_column(String(40))
    generation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    selected_variant: Mapped[str | None] = mapped_column(String(40))
    policy_status: Mapped[str | None] = mapped_column(String(20))
    policy_issues: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
