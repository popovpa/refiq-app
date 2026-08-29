from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.usage.models import AiUsage


class AiUsageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, usage: AiUsage) -> AiUsage:
        self.db.add(usage)
        await self.db.flush()
        return usage

    async def get_by_generation_id(self, generation_id: str) -> AiUsage | None:
        result = await self.db.execute(select(AiUsage).where(AiUsage.generation_id == generation_id))
        return result.scalar_one_or_none()
