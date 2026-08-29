from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.postback.models import PostbackCredential


class PostbackRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_by_business(self, business_id: int) -> PostbackCredential | None:
        result = await self.db.execute(
            select(PostbackCredential).where(
                PostbackCredential.business_id == business_id,
                PostbackCredential.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_hash(self, token_hash: str) -> PostbackCredential | None:
        result = await self.db.execute(
            select(PostbackCredential).where(
                PostbackCredential.token_hash == token_hash,
                PostbackCredential.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def add(self, credential: PostbackCredential) -> PostbackCredential:
        self.db.add(credential)
        await self.db.flush()
        return credential

    async def revoke(self, credential: PostbackCredential) -> None:
        credential.revoked_at = datetime.now(timezone.utc)

    async def mark_success(self, credential: PostbackCredential) -> None:
        credential.last_success_at = datetime.now(timezone.utc)
