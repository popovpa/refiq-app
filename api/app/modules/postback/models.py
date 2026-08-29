from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class PostbackCredential(Base):
    __tablename__ = "postback_credentials"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_suffix: Mapped[str] = mapped_column(String(4), nullable=False)
    created_by_user_id: Mapped[int | None] = fk_column("users.id", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
