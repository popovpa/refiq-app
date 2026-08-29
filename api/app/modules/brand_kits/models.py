from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    logo_asset_id: Mapped[int | None] = fk_column("assets.id", nullable=True)
    brand_colors: Mapped[list | None] = mapped_column(JSONB)
    tone_of_voice: Mapped[str | None] = mapped_column(Text)
    product_images: Mapped[list | None] = mapped_column(JSONB)
    allowed_claims: Mapped[list | None] = mapped_column(JSONB)
    forbidden_claims: Mapped[list | None] = mapped_column(JSONB)
    mandatory_disclaimers: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("business_id", name="uq_brand_kits_business_id"),)
