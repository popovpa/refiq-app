from datetime import datetime
from sqlalchemy import String, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"

    id: Mapped[int] = pk_column()
    user_id: Mapped[int] = fk_column("users.id", unique=True)
    legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BusinessPartner(Base):
    __tablename__ = "business_partners"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    partner_id: Mapped[int] = fk_column("partner_profiles.id")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("business_id", "partner_id", name="uq_business_partner"),
    )
