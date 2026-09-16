from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.data import CATEGORIES, VERTICALS
from app.modules.catalog.models import OfferCategory, OfferVertical


async def ensure_catalog(db: AsyncSession) -> dict[str, OfferCategory]:
    existing_verticals = {
        row.code: row for row in (await db.execute(select(OfferVertical))).scalars().all()
    }
    for index, (code, name_ru, name_en) in enumerate(VERTICALS):
        row = existing_verticals.get(code)
        if row is None:
            row = OfferVertical(
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                sort_order=index,
                is_active=True,
            )
            db.add(row)
            existing_verticals[code] = row
    await db.flush()

    existing_categories = {
        row.code: row for row in (await db.execute(select(OfferCategory))).scalars().all()
    }
    for index, (vertical_code, code, name_ru, name_en) in enumerate(CATEGORIES):
        row = existing_categories.get(code)
        vertical = existing_verticals[vertical_code]
        if row is None:
            row = OfferCategory(
                vertical_id=vertical.id,
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                sort_order=index,
                is_active=True,
            )
            db.add(row)
            existing_categories[code] = row
    await db.flush()
    return existing_categories
