from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )

    id: Mapped[int] = pk_column()
    user_id: Mapped[int] = fk_column("users.id")
    role_context: Mapped[str | None] = mapped_column(String(20), index=True)
    business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destination: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    dedupe_key: Mapped[str | None] = mapped_column(String(191))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
