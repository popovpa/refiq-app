from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class SdkScript(Base):
    __tablename__ = "sdk_scripts"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    site_id: Mapped[int | None] = fk_column("sites.id", nullable=True, unique=True)
    script_id: Mapped[str] = mapped_column(String(5), unique=True, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = fk_column("users.id", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
