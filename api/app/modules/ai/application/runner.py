from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from pydantic import BaseModel, ValidationError

from app.modules.ai.deps import get_usage_session_factory
from app.modules.ai.capabilities import Capability, EntityType, Operation
from app.modules.ai.errors import AiError, ai_invalid_response, ai_unavailable
from app.modules.ai.generation import GenerationResult, ImageGenerationRequest, StructuredGenerationRequest
from app.modules.ai.providers.selection import image_provider_name, image_usage_model, text_provider_name, text_usage_model
from app.modules.ai.resolver import get_provider_resolver
from app.modules.ai.usage.service import AiUsageService

logger = structlog.get_logger()


async def run_structured(
    *,
    schema: dict,
    schema_name: str,
    system_prompt: str,
    user_prompt: str,
    operation: Operation,
    prompt_version: str,
    user_id: int,
    entity_id: str | None = None,
    entity_type: EntityType | None = EntityType.OFFER,
    payload_model: type[BaseModel],
    generation_id: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    extra_metadata: dict | None = None,
) -> tuple[str, dict, GenerationResult]:
    generation_id = generation_id or str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    provider_name = text_provider_name()
    model_name = text_usage_model(model)

    async with get_usage_session_factory()() as usage_db:
        usage_service = AiUsageService(usage_db)
        usage = await usage_service.start(
            generation_id=generation_id,
            provider=provider_name,
            model=model_name,
            capability=Capability.STRUCTURED_GENERATION,
            operation=operation,
            prompt_version=prompt_version,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_metadata=extra_metadata,
        )
        await usage_db.commit()

        try:
            provider = get_provider_resolver().text(Capability.STRUCTURED_GENERATION)
            result = await provider.generate_structured(
                StructuredGenerationRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=schema,
                    schema_name=schema_name,
                    operation=operation.value,
                    prompt_version=prompt_version,
                    model=model,
                    reasoning_effort=reasoning_effort,
                )
            )
            if not result.structured_data:
                raise ai_invalid_response()
            try:
                payload = payload_model.model_validate(result.structured_data)
            except ValidationError as exc:
                raise ai_invalid_response() from exc
            await usage_service.complete(usage, result, started)
            await usage_db.commit()
            return generation_id, payload.model_dump(), result
        except Exception as exc:
            try:
                await usage_service.fail(
                    usage,
                    exc,
                    started,
                    retry_count=getattr(exc, "retry_count", 0),
                    provider_metadata=getattr(exc, "provider_metadata", None),
                )
                await usage_db.commit()
            except Exception:
                logger.error(
                    "ai_usage_persist_failed",
                    generation_id=generation_id,
                    operation=operation.value,
                )
            if isinstance(exc, AiError):
                raise
            raise ai_unavailable() from exc


async def run_image(
    *,
    prompt: str,
    aspect_ratio: str,
    image_format: str,
    operation: Operation,
    prompt_version: str,
    user_id: int,
    entity_id: str | None = None,
    entity_type: EntityType | None = EntityType.CREATIVE,
    n: int = 1,
    generation_id: str | None = None,
    extra_metadata: dict | None = None,
) -> tuple[str, GenerationResult]:
    generation_id = generation_id or str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    provider_name = image_provider_name()
    model_name = image_usage_model()

    async with get_usage_session_factory()() as usage_db:
        usage_service = AiUsageService(usage_db)
        usage = await usage_service.start(
            generation_id=generation_id,
            provider=provider_name,
            model=model_name,
            capability=Capability.IMAGE_GENERATION,
            operation=operation,
            prompt_version=prompt_version,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_metadata=extra_metadata,
        )
        await usage_db.commit()

        logger.info(
            "ai_image_prompt",
            generation_id=generation_id,
            operation=operation.value,
            provider=provider_name,
            model=model_name,
            aspect_ratio=aspect_ratio,
            image_format=image_format,
            prompt_version=prompt_version,
            entity_id=entity_id,
            prompt=prompt,
        )

        try:
            provider = get_provider_resolver().image(Capability.IMAGE_GENERATION)
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    image_format=image_format,
                    operation=operation.value,
                    prompt_version=prompt_version,
                    n=n,
                )
            )
            if not result.images:
                raise ai_invalid_response()
            try:
                await usage_service.complete(
                    usage,
                    result,
                    started,
                    image_metrics={
                        "asset_count": len(result.images),
                        "width": result.images[0].width,
                        "height": result.images[0].height,
                        "format": image_format,
                        "mime_type": result.images[0].mime_type,
                    },
                )
                await usage_db.commit()
            except Exception:
                logger.error(
                    "ai_usage_persist_failed",
                    generation_id=generation_id,
                    operation=operation.value,
                )
                try:
                    await usage_db.rollback()
                except Exception:
                    pass
            return generation_id, result
        except Exception as exc:
            logger.warning(
                "ai_image_failed",
                generation_id=generation_id,
                operation=operation.value,
                model=model_name,
                error_type=type(exc).__name__,
                error_code=getattr(exc, "code", None),
                error_message=getattr(exc, "message", str(exc))[:300],
                provider_metadata=getattr(exc, "provider_metadata", None),
            )
            try:
                await usage_service.fail(
                    usage,
                    exc,
                    started,
                    retry_count=getattr(exc, "retry_count", 0),
                    provider_metadata=getattr(exc, "provider_metadata", None),
                )
                await usage_db.commit()
            except Exception:
                logger.error(
                    "ai_usage_persist_failed",
                    generation_id=generation_id,
                    operation=operation.value,
                )
            if isinstance(exc, AiError):
                raise
            raise ai_unavailable() from exc
