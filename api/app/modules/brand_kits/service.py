from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brand_kits.models import BrandKit


async def get_brand_kit(db: AsyncSession, business_id: int) -> BrandKit | None:
    return (
        await db.execute(select(BrandKit).where(BrandKit.business_id == business_id))
    ).scalar_one_or_none()


async def get_or_create_brand_kit(db: AsyncSession, business_id: int) -> BrandKit:
    existing = await get_brand_kit(db, business_id)
    if existing:
        return existing
    kit = BrandKit(business_id=business_id)
    db.add(kit)
    await db.flush()
    return kit
