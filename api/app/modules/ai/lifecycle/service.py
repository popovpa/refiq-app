from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AiGenerationStatus
from app.modules.ai.lifecycle.models import AiGeneration


class AiGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        generation_id: str,
        user_id: int,
        operation: str,
        offer_id: int | None = None,
        creative_id: int | None = None,
        prompt_version: str | None = None,
        request: dict | None = None,
        status: str = AiGenerationStatus.PROCESSING.value,
    ) -> AiGeneration:
        row = AiGeneration(
            generation_id=generation_id,
            user_id=user_id,
            offer_id=offer_id,
            creative_id=creative_id,
            operation=operation,
            status=status,
            prompt_version=prompt_version,
            request=request,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get(self, generation_id: str) -> AiGeneration | None:
        return (
            await self.db.execute(select(AiGeneration).where(AiGeneration.generation_id == generation_id))
        ).scalar_one_or_none()

    async def complete(
        self,
        row: AiGeneration,
        result: dict,
        *,
        generated_variants: int | None = None,
    ) -> None:
        row.status = AiGenerationStatus.COMPLETED.value
        row.result = result
        row.generated_variants = generated_variants
        row.completed_at = datetime.now(timezone.utc)
        row.error_code = None
        row.error_message = None

    async def fail(self, row: AiGeneration, *, error_code: str, error_message: str) -> None:
        row.status = AiGenerationStatus.FAILED.value
        row.error_code = error_code
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
