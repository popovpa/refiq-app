from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.ai.capabilities import Capability, EntityType, Operation
from app.modules.ai.errors import AiError
from app.modules.ai.generation import GenerationResult
from app.modules.ai.usage.models import AiUsage
from app.modules.ai.usage.pricing import estimate_cost
from app.modules.ai.usage.repository import AiUsageRepository

logger = structlog.get_logger()


class AiUsageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AiUsageRepository(db)

    async def start(
        self,
        *,
        generation_id: str,
        provider: str,
        model: str,
        capability: Capability,
        operation: Operation,
        prompt_version: str,
        user_id: int | None,
        entity_type: EntityType | None = None,
        entity_id: str | None = None,
        extra_metadata: dict | None = None,
    ) -> AiUsage:
        usage = AiUsage(
            generation_id=generation_id,
            provider=provider,
            model=model,
            capability=capability.value,
            operation=operation.value,
            user_id=user_id,
            entity_type=entity_type.value if entity_type else None,
            entity_id=entity_id,
            prompt_version=prompt_version,
            started_at=datetime.now(timezone.utc),
            status="running",
            retry_count=0,
            provider_metadata=extra_metadata,
        )
        return await self.repository.add(usage)

    async def complete(
        self,
        usage: AiUsage,
        result: GenerationResult,
        started: datetime,
        *,
        image_metrics: dict[str, Any] | None = None,
    ) -> None:
        finished = datetime.now(timezone.utc)
        usage.status = "succeeded"
        usage.completed_at = finished
        usage.provider = result.provider
        usage.model = result.model
        usage.input_tokens = result.usage.input_tokens
        usage.output_tokens = result.usage.output_tokens
        usage.total_tokens = result.usage.total_tokens
        usage.cached_input_tokens = result.usage.cached_input_tokens
        usage.reasoning_tokens = result.usage.reasoning_tokens
        usage.provider_request_id = _as_request_id(result.usage.provider_request_id)
        usage.retry_count = result.retry_count
        usage.latency_ms = int((finished - started).total_seconds() * 1000)
        metadata = {
            **(usage.provider_metadata or {}),
            **result.provider_metadata,
            **(result.usage.metadata or {}),
        }
        if image_metrics:
            metadata["image"] = image_metrics
            usage.asset_count = image_metrics.get("asset_count")
            usage.image_width = image_metrics.get("width")
            usage.image_height = image_metrics.get("height")
            usage.image_format = image_metrics.get("format")
        elif result.images:
            first = result.images[0]
            usage.asset_count = len(result.images)
            usage.image_width = first.width
            usage.image_height = first.height
            metadata["image"] = {
                "asset_count": len(result.images),
                "width": first.width,
                "height": first.height,
                "mime_type": first.mime_type,
            }
        usage.provider_metadata = metadata
        usage.estimated_cost = estimate_cost(
            provider=result.provider,
            model=result.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )
        usage.currency = "USD" if usage.estimated_cost is not None else None
        _log_usage(usage)

    async def fail(
        self,
        usage: AiUsage,
        error: Exception,
        started: datetime,
        *,
        retry_count: int = 0,
        provider_metadata: dict[str, Any] | None = None,
    ) -> None:
        finished = datetime.now(timezone.utc)
        usage.status = "failed"
        usage.completed_at = finished
        usage.retry_count = retry_count
        usage.latency_ms = int((finished - started).total_seconds() * 1000)
        if isinstance(error, AppError):
            usage.error_code = error.code
            usage.error_type = error.__class__.__name__
        else:
            usage.error_code = "INTERNAL_ERROR"
            usage.error_type = error.__class__.__name__
        if provider_metadata:
            usage.provider_metadata = {**(usage.provider_metadata or {}), **provider_metadata}
        _log_usage(usage)

    async def record_feedback(
        self,
        generation_id: str,
        *,
        user_id: int,
        outcome: str,
        generated_fields_count: int | None = None,
        accepted_fields_count: int | None = None,
        modified_fields_count: int | None = None,
        rejected_fields_count: int | None = None,
    ) -> AiUsage:
        usage = await self.repository.get_by_generation_id(generation_id)
        if not usage or usage.user_id != user_id:
            raise AppError("AI_GENERATION_NOT_FOUND", "Generation not found", 404)
        usage.feedback_outcome = outcome
        usage.generated_fields_count = generated_fields_count
        usage.accepted_fields_count = accepted_fields_count
        usage.modified_fields_count = modified_fields_count
        usage.rejected_fields_count = rejected_fields_count
        return usage


def _as_request_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)[:120]


def _log_usage(usage: AiUsage) -> None:
    metadata = usage.provider_metadata or {}
    logger.info(
        "ai_generation",
        generation_id=usage.generation_id,
        provider=usage.provider,
        model=usage.model,
        operation=usage.operation,
        latency_ms=usage.latency_ms,
        status=usage.status,
        error_code=usage.error_code,
        endpoint=metadata.get("endpoint"),
        http_status=metadata.get("http_status"),
        provider_error_code=metadata.get("provider_error_code"),
        provider_error_message=metadata.get("provider_error_message"),
    )
