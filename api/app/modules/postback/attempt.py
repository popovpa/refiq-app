from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class PostbackAttemptResult:
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class PostbackAttempt(Base):
    __tablename__ = "postback_attempts"
    __table_args__ = (
        Index("ix_postback_attempts_rqcid", "rqcid"),
        Index("ix_postback_attempts_received_at", "received_at"),
    )

    id: Mapped[int] = pk_column()
    business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    rqcid: Mapped[str | None] = mapped_column(String(12))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    conversion_id: Mapped[int | None] = fk_column("conversions.id", nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
