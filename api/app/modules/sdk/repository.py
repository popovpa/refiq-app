from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sdk.models import SdkScript


class SdkScriptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_business(self, business_id: int) -> SdkScript | None:
        scripts = await self.list_by_business(business_id)
        return scripts[0] if scripts else None

    async def list_by_business(self, business_id: int) -> list[SdkScript]:
        result = await self.db.execute(
            select(SdkScript).where(SdkScript.business_id == business_id).order_by(SdkScript.id.asc())
        )
        return list(result.scalars().all())

    async def exists_script_id(self, script_id: str) -> bool:
        value = await self.db.scalar(select(SdkScript.id).where(SdkScript.script_id == script_id))
        return value is not None

    async def get_by_script_id(self, script_id: str) -> SdkScript | None:
        result = await self.db.execute(select(SdkScript).where(SdkScript.script_id == script_id))
        return result.scalar_one_or_none()

    async def get_by_site_id(self, site_id: int) -> SdkScript | None:
        result = await self.db.execute(select(SdkScript).where(SdkScript.site_id == site_id))
        return result.scalar_one_or_none()

    async def mark_success(self, script_id: str) -> None:
        script = await self.get_by_script_id(script_id)
        if script:
            script.last_success_at = datetime.now(timezone.utc)

    async def add(self, script: SdkScript) -> SdkScript:
        self.db.add(script)
        await self.db.flush()
        return script
