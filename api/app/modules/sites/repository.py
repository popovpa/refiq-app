from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sites.models import Site


class SiteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_business(self, business_id: int) -> list[Site]:
        result = await self.db.execute(
            select(Site).where(Site.business_id == business_id).order_by(Site.created_at.asc(), Site.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, site_id: int) -> Site | None:
        result = await self.db.execute(select(Site).where(Site.id == site_id))
        return result.scalar_one_or_none()

    async def get_owned(self, business_id: int, site_id: int) -> Site | None:
        result = await self.db.execute(
            select(Site).where(Site.id == site_id, Site.business_id == business_id)
        )
        return result.scalar_one_or_none()

    async def get_by_business_domain(self, business_id: int, domain: str) -> Site | None:
        result = await self.db.execute(
            select(Site).where(Site.business_id == business_id, Site.domain == domain)
        )
        return result.scalar_one_or_none()

    async def get_by_site_key(self, site_key: str) -> Site | None:
        result = await self.db.execute(select(Site).where(Site.site_key == site_key))
        return result.scalar_one_or_none()

    async def exists_site_key(self, site_key: str) -> bool:
        value = await self.db.scalar(select(Site.id).where(Site.site_key == site_key))
        return value is not None

    async def add(self, site: Site) -> Site:
        self.db.add(site)
        await self.db.flush()
        return site

    async def delete(self, site: Site) -> None:
        await self.db.delete(site)
        await self.db.flush()
