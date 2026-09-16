from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import fk_column, pk_column


class OfferVertical(Base):
    __tablename__ = "offer_verticals"

    id: Mapped[int] = pk_column()
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    categories: Mapped[list["OfferCategory"]] = relationship(back_populates="vertical")


class OfferCategory(Base):
    __tablename__ = "offer_categories"
    __table_args__ = (UniqueConstraint("code", name="uq_offer_categories_code"),)

    id: Mapped[int] = pk_column()
    vertical_id: Mapped[int] = fk_column("offer_verticals.id")
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name_ru: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    vertical: Mapped[OfferVertical] = relationship(back_populates="categories", lazy="joined")
