from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AiGenerationStatus, CreativeType
from app.core.exceptions import AppError
from app.modules.ai.application.runner import run_image, run_structured
from app.modules.ai.capabilities import EntityType, Operation
from app.modules.ai.application.creative.promo_copy_guard import assert_customer_facing_copy
from app.modules.ai.context.offer_context import OfferPromotionContextBuilder
from app.modules.ai.context.promo_payload import text_generation_payload
from app.modules.ai.dto import CreativeRewritePayload, CreativeSocialPayload, CreativeTextPayload
from app.modules.ai.errors import AiError
from app.modules.ai.jobs import GenerationJobRunner
from app.modules.ai.lifecycle.service import AiGenerationService
from app.modules.ai.prompts import creative as prompts
from app.modules.ai.safety.operations import AiOperation
from app.modules.ai.safety.output_guard import guard_output
from app.modules.ai.safety.pipeline import evaluate_user_guidance
from app.modules.ai.safety.policy import get_operation_policy
from app.modules.ai.safety.verified_context import build_verified_context
from app.modules.ai.schemas import creative_rewrite_schema, creative_social_schema, creative_text_schema
from app.modules.assets.service import AssetService
from app.modules.brand_kits.service import get_brand_kit
from app.modules.creatives.models import Creative
from app.modules.creatives.normalize import BANNER_ASPECT, clamp_variants
from app.modules.creatives.policy import CreativePolicyValidator
from app.modules.offers.models import Offer
from app.modules.products.models import Product


async def generate_creative(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    creative_type: str,
    instruction: str = "",
    variants: int | None = None,
    channel: str | None = None,
    image_format: str | None = None,
    language: str | None = None,
    goal: str | None = None,
    style: str | None = None,
    job_runner: GenerationJobRunner | None = None,
) -> dict:
    count = clamp_variants(creative_type, variants)
    evaluated = await evaluate_user_guidance(
        operation=AiOperation.GENERATE_CREATIVE,
        guidance=instruction,
        user_id=user_id,
        offer_id=offer.id,
        require_input=False,
    )
    instruction = evaluated.guidance
    if creative_type == CreativeType.BANNER.value:
        return await start_banner_generation(
            db,
            offer=offer,
            user_id=user_id,
            instruction=instruction,
            image_format=image_format or "square_1_1",
            language=language,
            job_runner=job_runner,
        )
    if creative_type == CreativeType.SOCIAL_POST.value:
        return await generate_social_post(
            db,
            offer=offer,
            user_id=user_id,
            instruction=instruction,
            variants=count,
            channel=channel or "telegram",
            language=language,
            goal=goal,
            style=style,
        )
    return await generate_creative_text(
        db,
        offer=offer,
        user_id=user_id,
        instruction=instruction,
        variants=count,
        channel=channel,
        language=language,
        goal=goal,
        style=style,
    )


async def generate_creative_text(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    instruction: str,
    variants: int,
    channel: str | None,
    language: str | None,
    goal: str | None,
    style: str | None,
) -> dict:
    return await _generate_text_family(
        db,
        offer=offer,
        user_id=user_id,
        instruction=instruction,
        variants=variants,
        channel=channel,
        language=language,
        goal=goal,
        style=style,
        creative_type=CreativeType.TEXT.value,
        operation=Operation.CREATIVE_TEXT_GENERATION,
        prompt_version=prompts.TEXT_V1,
        system_prompt=prompts.text_system_prompt(),
        schema=creative_text_schema(),
        schema_name="creative_text",
        payload_model=CreativeTextPayload,
        require_cta=False,
    )


async def generate_social_post(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    instruction: str,
    variants: int,
    channel: str | None,
    language: str | None,
    goal: str | None,
    style: str | None,
) -> dict:
    return await _generate_text_family(
        db,
        offer=offer,
        user_id=user_id,
        instruction=instruction,
        variants=variants,
        channel=channel,
        language=language,
        goal=goal,
        style=style,
        creative_type=CreativeType.SOCIAL_POST.value,
        operation=Operation.CREATIVE_SOCIAL_POST_GENERATION,
        prompt_version=prompts.SOCIAL_V1,
        system_prompt=prompts.social_system_prompt(),
        schema=creative_social_schema(),
        schema_name="creative_social_post",
        payload_model=CreativeSocialPayload,
        require_cta=True,
    )


async def rewrite_creative(
    db: AsyncSession,
    *,
    offer: Offer,
    creative: Creative,
    user_id: int,
    instruction: str,
) -> dict:
    if creative.type == CreativeType.BANNER.value:
        raise AppError("CREATIVE_IMAGE_EDIT_UNAVAILABLE", "Banner image edit is not available yet", 501)
    product = await _product(db, offer)
    context = await OfferPromotionContextBuilder().build(
        db,
        offer,
        product=product,
        channel=creative.channel,
        image_format=creative.format,
        language=creative.language,
        instruction=instruction,
    )
    context["current"] = creative.text_content or {}
    evaluated = await evaluate_user_guidance(
        operation=AiOperation.REWRITE_CREATIVE,
        guidance=instruction,
        user_id=user_id,
        offer_id=offer.id,
    )
    instruction = evaluated.guidance
    context["instruction"] = instruction or None
    generation_id = str(uuid.uuid4())
    try:
        _, payload, _result = await run_structured(
            schema=creative_rewrite_schema(),
            schema_name="creative_rewrite",
            system_prompt=prompts.rewrite_system_prompt(),
            user_prompt=json.dumps({**text_generation_payload(context, None), "current": context["current"]}, ensure_ascii=False),
            operation=Operation.CREATIVE_TEXT_REWRITE,
            prompt_version=prompts.REWRITE_V1,
            user_id=user_id,
            entity_id=str(creative.id),
            entity_type=EntityType.CREATIVE,
            payload_model=CreativeRewritePayload,
            generation_id=generation_id,
        )
        assert_customer_facing_copy(payload, product_context=context.get("productContext"))
        product_ctx = context.get("productContext") or {}
        verified = build_verified_context(
            field="creative",
            current_value=json.dumps(context.get("current") or {}, ensure_ascii=False),
            offer_context={
                "name": product_ctx.get("name") or product_ctx.get("productName"),
                "description": product_ctx.get("description") or product_ctx.get("shortDescription"),
                "category": product_ctx.get("category"),
                "geo": product_ctx.get("geo"),
                "product_url": product_ctx.get("url") or product_ctx.get("productUrl"),
            },
        )
        guard_output(
            payload,
            operation=AiOperation.REWRITE_CREATIVE,
            user_id=user_id,
            offer_id=offer.id,
            verified_context=verified,
            policy=get_operation_policy(AiOperation.REWRITE_CREATIVE),
        )
    except Exception as exc:
        await _record_generation(
            db,
            generation_id=generation_id,
            user_id=user_id,
            operation=Operation.CREATIVE_TEXT_REWRITE.value,
            offer_id=offer.id,
            creative_id=creative.id,
            prompt_version=prompts.REWRITE_V1,
            request={"instruction": instruction, "type": creative.type},
            error=exc,
        )
        if isinstance(exc, AiError):
            raise
        raise
    brand_kit = await get_brand_kit(db, offer.business_id)
    policy = CreativePolicyValidator().validate_text(
        payload,
        offer=offer,
        brand_kit=brand_kit,
        require_cta=creative.type == CreativeType.SOCIAL_POST.value,
    )
    await _record_generation(
        db,
        generation_id=generation_id,
        user_id=user_id,
        operation=Operation.CREATIVE_TEXT_REWRITE.value,
        offer_id=offer.id,
        creative_id=creative.id,
        prompt_version=prompts.REWRITE_V1,
        request={"instruction": instruction, "type": creative.type},
        result={"proposed": payload, "policy": policy},
        generated_variants=1,
    )
    return {
        "generation_id": generation_id,
        "status": AiGenerationStatus.COMPLETED.value,
        "proposed": payload,
        "policy": policy,
    }


async def start_banner_generation(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    instruction: str,
    image_format: str,
    language: str | None,
    job_runner: GenerationJobRunner | None,
) -> dict:
    if job_runner is None:
        raise AppError("AI_UNAVAILABLE", "Async generation is not configured", 503)
    generation_id = str(uuid.uuid4())
    await AiGenerationService(db).create(
        generation_id=generation_id,
        user_id=user_id,
        operation=Operation.CREATIVE_IMAGE_GENERATION.value,
        offer_id=offer.id,
        prompt_version=prompts.BANNER_V1,
        request={
            "type": CreativeType.BANNER.value,
            "format": image_format,
            "instruction": instruction,
            "language": language or "ru",
        },
    )
    job_runner.submit(execute_banner_generation, generation_id)
    return {
        "generation_id": generation_id,
        "status": AiGenerationStatus.PROCESSING.value,
    }


async def execute_banner_generation(generation_id: str) -> None:
    from app.modules.ai.deps import get_usage_session_factory

    async with get_usage_session_factory()() as db:
        lifecycle = AiGenerationService(db)
        row = await lifecycle.get(generation_id)
        if not row or not row.offer_id:
            return
        offer = (await db.execute(select(Offer).where(Offer.id == row.offer_id))).scalar_one_or_none()
        if not offer:
            await lifecycle.fail(row, error_code="OFFER_NOT_FOUND", error_message="Offer not found")
            await db.commit()
            return
        request = row.request or {}
        image_format = request.get("format") or "square_1_1"
        instruction = request.get("instruction") or ""
        try:
            product = await _product(db, offer)
            context = await OfferPromotionContextBuilder().build(
                db,
                offer,
                product=product,
                image_format=image_format,
                language=request.get("language"),
                instruction=instruction,
            )
            prompt = prompts.banner_prompt(context, instruction)
            _generation_id, result = await run_image(
                prompt=prompt,
                aspect_ratio=BANNER_ASPECT.get(image_format, "1:1"),
                image_format=image_format,
                operation=Operation.CREATIVE_IMAGE_GENERATION,
                prompt_version=prompts.BANNER_V1,
                user_id=row.user_id,
                entity_id=str(offer.id),
                entity_type=EntityType.OFFER,
                n=1,
                generation_id=generation_id,
            )
            assets = AssetService(db)
            variants = []
            for image in result.images:
                asset = await assets.store_image(
                    image.data,
                    mime_type=image.mime_type,
                    width=image.width,
                    height=image.height,
                )
                variants.append(
                    {
                        "asset_id": asset.id,
                        "width": image.width,
                        "height": image.height,
                        "mime_type": image.mime_type,
                        "format": image_format,
                    }
                )
            await lifecycle.complete(
                row,
                {"type": CreativeType.BANNER.value, "variants": variants},
                generated_variants=len(variants),
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            row = await lifecycle.get(generation_id)
            if row and row.status == AiGenerationStatus.PROCESSING.value:
                await lifecycle.fail(
                    row,
                    error_code=_error_code(exc),
                    error_message="Image generation failed",
                )
                await db.commit()


async def serialize_generation(row) -> dict:
    payload = {
        "generation_id": row.generation_id,
        "status": row.status,
        "operation": row.operation,
        "offer_id": row.offer_id,
        "creative_id": row.creative_id,
    }
    if row.status == AiGenerationStatus.FAILED.value:
        payload["error"] = {"code": row.error_code, "message": row.error_message}
        return payload
    result = row.result or {}
    if "variants" in result:
        payload["variants"] = result["variants"]
    if "policy" in result:
        payload["policy"] = result["policy"]
    if "proposed" in result:
        payload["proposed"] = result["proposed"]
    if result.get("type") == "promo_kit":
        payload["created_ids"] = result.get("created_ids") or []
        payload["errors"] = result.get("errors") or []
    return payload


async def _generate_text_family(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    instruction: str,
    variants: int,
    channel: str | None,
    language: str | None,
    goal: str | None,
    style: str | None,
    creative_type: str,
    operation: Operation,
    prompt_version: str,
    system_prompt: str,
    schema: dict,
    schema_name: str,
    payload_model,
    require_cta: bool,
) -> dict:
    product = await _product(db, offer)
    context = await OfferPromotionContextBuilder().build(
        db,
        offer,
        product=product,
        channel=channel,
        language=language,
        instruction=instruction,
        goal=goal,
        style=style,
    )
    context["variants"] = variants
    generation_id = str(uuid.uuid4())
    request = {
        "type": creative_type,
        "channel": channel,
        "instruction": instruction,
        "variants": variants,
        "goal": goal,
        "style": style,
    }
    try:
        _, payload, _result = await run_structured(
            schema=schema,
            schema_name=schema_name,
            system_prompt=system_prompt,
            user_prompt=json.dumps({**text_generation_payload(context, None), "variants": variants}, ensure_ascii=False),
            operation=operation,
            prompt_version=prompt_version,
            user_id=user_id,
            entity_id=str(offer.id),
            entity_type=EntityType.OFFER,
            payload_model=payload_model,
            generation_id=generation_id,
        )
        assert_customer_facing_copy(payload, product_context=context.get("productContext"))
        product_ctx = context.get("productContext") or {}
        verified = build_verified_context(
            field="creative",
            current_value="",
            offer_context={
                "name": product_ctx.get("name") or product_ctx.get("productName"),
                "description": product_ctx.get("description") or product_ctx.get("shortDescription"),
                "category": product_ctx.get("category"),
                "geo": product_ctx.get("geo"),
                "product_url": product_ctx.get("url") or product_ctx.get("productUrl"),
            },
        )
        guard_output(
            payload,
            operation=AiOperation.GENERATE_CREATIVE,
            user_id=user_id,
            offer_id=offer.id,
            verified_context=verified,
            policy=get_operation_policy(AiOperation.GENERATE_CREATIVE),
        )
    except Exception as exc:
        await _record_generation(
            db,
            generation_id=generation_id,
            user_id=user_id,
            operation=operation.value,
            offer_id=offer.id,
            prompt_version=prompt_version,
            request=request,
            error=exc,
        )
        if isinstance(exc, AiError):
            raise
        raise
    brand_kit = await get_brand_kit(db, offer.business_id)
    validator = CreativePolicyValidator()
    annotated = []
    for item in payload.get("variants") or []:
        policy = validator.validate_text(
            item,
            offer=offer,
            brand_kit=brand_kit,
            require_cta=require_cta,
        )
        annotated.append({**item, "policy": policy})
    annotated = annotated[:variants]
    await _record_generation(
        db,
        generation_id=generation_id,
        user_id=user_id,
        operation=operation.value,
        offer_id=offer.id,
        prompt_version=prompt_version,
        request=request,
        result={"type": creative_type, "variants": annotated},
        generated_variants=len(annotated),
    )
    return {
        "generation_id": generation_id,
        "status": AiGenerationStatus.COMPLETED.value,
        "variants": annotated,
    }


async def _record_generation(
    db: AsyncSession,
    *,
    generation_id: str,
    user_id: int,
    operation: str,
    offer_id: int | None,
    prompt_version: str | None,
    request: dict | None,
    creative_id: int | None = None,
    result: dict | None = None,
    generated_variants: int | None = None,
    error: Exception | None = None,
) -> None:
    lifecycle = AiGenerationService(db)
    row = await lifecycle.create(
        generation_id=generation_id,
        user_id=user_id,
        operation=operation,
        offer_id=offer_id,
        creative_id=creative_id,
        prompt_version=prompt_version,
        request=request,
        status=AiGenerationStatus.PROCESSING.value,
    )
    if error is not None:
        await lifecycle.fail(row, error_code=_error_code(error), error_message="Creative generation failed")
        return
    await lifecycle.complete(row, result or {}, generated_variants=generated_variants)


async def _product(db: AsyncSession, offer: Offer) -> Product | None:
    if not offer.product_id:
        return None
    return (await db.execute(select(Product).where(Product.id == offer.product_id))).scalar_one_or_none()


def _error_code(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    return "AI_UNAVAILABLE"
