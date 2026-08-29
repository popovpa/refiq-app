from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class AiGeneration(Base):
    """Pollable generation lifecycle. Telemetry stays in ai_usage."""

    __tablename__ = "ai_generations"

    id: Mapped[int] = pk_column()
    generation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = fk_column("users.id")
    offer_id: Mapped[int | None] = fk_column("offers.id", nullable=True)
    creative_id: Mapped[int | None] = fk_column("creatives.id", nullable=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    request: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    generated_variants: Mapped[int | None] = mapped_column(Integer)
    selected_variant: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
