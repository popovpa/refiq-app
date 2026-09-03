from __future__ import annotations

import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collections.abc import Awaitable, Callable

from app.common.enums import (
    BannerFormat,
    CreativeChannel,
    CreativeSource,
    CreativeStatus,
    CreativeType,
)
from app.core.exceptions import AppError
from app.modules.ai.application.runner import run_image, run_structured
from app.modules.ai.capabilities import EntityType, Operation
from app.modules.ai.application.creative.promo_copy_guard import (
    assert_customer_facing_copy,
    looks_like_affiliate_recruiting,
    strip_affiliate_language,
)
from app.modules.ai.application.creative.promo_image_prompt import normalize_image_prompt
from app.modules.ai.safety.image_prompt import ImagePromptValidator
from app.modules.ai.safety.operations import AiOperation, InputSource
from app.modules.ai.safety.pipeline import inspect_untrusted_text
from app.modules.ai.context.offer_context import OfferPromotionContextBuilder, PURPOSE_CUSTOMER_ACQUISITION
from app.modules.ai.context.promo_payload import brief_user_payload, text_generation_payload
from app.modules.ai.dto import (
    PromoBriefPayload,
    PromoImageSpecPayload,
    PromoKitTextsPayload,
    PromoMetaPayload,
    PromoSingleTextPayload,
    PromoSocialPostsPayload,
    PromoTikTokPayload,
    PromoYandexPayload,
)
from app.modules.ai.errors import AiError
from app.modules.ai.jobs import GenerationJobRunner
from app.modules.ai.prompts import promo as prompts
from app.modules.ai.providers.selection import promo_reasoning, promo_text_model
from app.modules.ai.schemas import (
    promo_brief_schema,
    promo_image_spec_schema,
    promo_kit_texts_schema,
    promo_meta_schema,
    promo_single_text_schema,
    promo_social_posts_schema,
    promo_tiktok_schema,
    promo_yandex_schema,
)
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.creatives.models import Creative
from app.modules.creatives.normalize import BANNER_ASPECT
from app.modules.creatives.promo_catalog import DEFAULT_QR_LAYOUT, PromoSlot, SLOTS
from app.modules.creatives.service import CreativeService
from app.modules.offers.models import Offer
from app.modules.products.models import Product

logger = structlog.get_logger()
PROMO_IMAGE_COUNT = 1
PROMO_OBJECT_PREFIX = "offers-promo"
TEXT_SLOTS = {
    "universal_ad": {
        "title": "Универсальный рекламный текст",
        "type": CreativeType.TEXT.value,
        "channel": CreativeChannel.GENERAL.value,
    },
    "short_ad": {
        "title": "Короткий рекламный текст",
        "type": CreativeType.TEXT.value,
        "channel": CreativeChannel.GENERAL.value,
    },
    "headlines": {
        "title": "Заголовки",
        "type": CreativeType.TEXT.value,
        "channel": CreativeChannel.GENERAL.value,
    },
    "descriptions": {
        "title": "Короткие описания",
        "type": CreativeType.TEXT.value,
        "channel": CreativeChannel.GENERAL.value,
    },
    "telegram_posts": {
        "title": "Telegram post",
        "type": CreativeType.SOCIAL_POST.value,
        "channel": CreativeChannel.TELEGRAM.value,
    },
    "vk_posts": {
        "title": "VK post",
        "type": CreativeType.SOCIAL_POST.value,
        "channel": CreativeChannel.VK.value,
    },
}


def promo_model(*, fast: bool = False) -> str:
    return promo_text_model(fast=fast)


def promo_object_key(offer_id: int, material_id: int, *, suffix: str | None = None) -> str:
    name = str(material_id) if not suffix else f"{material_id}-{suffix}"
    return f"{PROMO_OBJECT_PREFIX}/{offer_id}/{name}.png"


async def start_promo_kit(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    job_runner: GenerationJobRunner | None,
    slots: list[str] | None = None,
    qr_tracking_link_id: int | None = None,
) -> dict:
    from app.modules.ai.application.creative.promo_worker import start_promo_kit as start_run

    return await start_run(
        db,
        offer=offer,
        user_id=user_id,
        job_runner=job_runner,
        slots=slots,
        qr_tracking_link_id=qr_tracking_link_id,
    )


def promo_error_code(exc: Exception) -> str:
    return _error_code(exc)


def promo_error_message(exc: Exception, fallback: str) -> str:
    if isinstance(exc, AppError):
        detail = ""
        if isinstance(exc, AiError):
            detail = str((exc.provider_metadata or {}).get("provider_error_message") or "").strip()
        if detail:
            return f"{exc.message}: {detail}"[:500]
        return exc.message
    return fallback


def _usage_meta(*, run_id: int | None, item_id: int | None, offer_id: int) -> dict:
    return {
        "generation_run_id": run_id,
        "generation_item_id": item_id,
        "offer_id": offer_id,
    }


async def build_offer_snapshot(db: AsyncSession, offer: Offer, *, user_id: int | None = None) -> dict:
    product = await _product(db, offer)
    snapshot = await OfferPromotionContextBuilder().build(db, offer, product=product, language="ru")
    product_context = snapshot.get("productContext") or {}
    inspect_untrusted_text(
        " ".join(
            str(product_context.get(key) or "")
            for key in ("name", "description")
        ),
        operation=AiOperation.GENERATE_PROMOTION_BRIEF,
        source=InputSource.OFFER_FIELD,
        user_id=user_id,
        offer_id=offer.id,
    )
    return snapshot


async def generate_brief_from_snapshot(
    *,
    snapshot: dict,
    user_id: int,
    offer_id: int,
    run_id: int,
) -> dict:
    _, brief, _result = await run_structured(
        schema=promo_brief_schema(),
        schema_name="promo_brief",
        system_prompt=prompts.brief_system_prompt(),
        user_prompt=json.dumps(brief_user_payload(snapshot), ensure_ascii=False),
        operation=Operation.PROMO_BRIEF_GENERATE,
        prompt_version=prompts.BRIEF_V1,
        user_id=user_id,
        entity_id=str(offer_id),
        entity_type=EntityType.OFFER,
        payload_model=PromoBriefPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=True),
        extra_metadata=_usage_meta(run_id=run_id, item_id=None, offer_id=offer_id),
    )
    return _sanitize_brief(brief, snapshot)


async def generate_slot_payload(
    *,
    offer_id: int,
    user_id: int,
    context: dict,
    brief: dict,
    slot: PromoSlot,
    run_id: int,
    item_id: int,
) -> dict:
    payload = text_generation_payload(context, brief, slot.id)
    extra = _usage_meta(run_id=run_id, item_id=item_id, offer_id=offer_id)
    if slot.kind == "yandex":
        _, data, _result = await run_structured(
            schema=promo_yandex_schema(),
            schema_name="promo_yandex_direct",
            system_prompt=prompts.yandex_direct_system_prompt(),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=Operation.PROMO_YANDEX_GENERATE,
            prompt_version=prompts.YANDEX_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoYandexPayload,
            model=promo_model(),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        assert_customer_facing_copy(data, product_context=context.get("productContext"))
        return data
    if slot.kind == "search_ads":
        _, data, _result = await run_structured(
            schema=promo_yandex_schema(),
            schema_name="promo_google_ads",
            system_prompt=prompts.google_ads_system_prompt(),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=Operation.PROMO_TEXT_GENERATE,
            prompt_version=prompts.GOOGLE_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoYandexPayload,
            model=promo_model(),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        assert_customer_facing_copy(data, product_context=context.get("productContext"))
        return data
    if slot.kind == "meta":
        _, data, _result = await run_structured(
            schema=promo_meta_schema(),
            schema_name="promo_meta_ads",
            system_prompt=prompts.meta_ads_system_prompt(),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=Operation.PROMO_TEXT_GENERATE,
            prompt_version=prompts.META_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoMetaPayload,
            model=promo_model(),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        assert_customer_facing_copy(data, product_context=context.get("productContext"))
        return data
    if slot.kind == "tiktok":
        _, data, _result = await run_structured(
            schema=promo_tiktok_schema(),
            schema_name="promo_tiktok_ads",
            system_prompt=prompts.tiktok_ads_system_prompt(),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=Operation.PROMO_TEXT_GENERATE,
            prompt_version=prompts.TIKTOK_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoTikTokPayload,
            model=promo_model(),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        assert_customer_facing_copy(data, product_context=context.get("productContext"))
        return data
    if slot.kind == "social":
        _, data, _result = await run_structured(
            schema=promo_social_posts_schema(),
            schema_name="promo_social_posts",
            system_prompt=prompts.social_posts_system_prompt(slot.id),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=Operation.PROMO_TEXT_GENERATE,
            prompt_version=prompts.SINGLE_TEXT_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoSocialPostsPayload,
            model=promo_model(),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        assert_customer_facing_copy(data, product_context=context.get("productContext"))
        return data
    _, data, _result = await run_structured(
        schema=promo_single_text_schema(),
        schema_name="promo_single_text",
        system_prompt=prompts.single_text_system_prompt(slot.id),
        user_prompt=json.dumps(payload, ensure_ascii=False),
        operation=Operation.PROMO_TEXT_GENERATE,
        prompt_version=prompts.SINGLE_TEXT_V1,
        user_id=user_id,
        entity_id=str(offer_id),
        entity_type=EntityType.OFFER,
        payload_model=PromoSingleTextPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=False),
        extra_metadata=extra,
    )
    assert_customer_facing_copy(data, product_context=context.get("productContext"))
    return data


def _validated_image_prompt(
    prompt: str,
    *,
    product_context: dict | None,
    user_id: int | None = None,
    offer_id: int | None = None,
) -> str:
    return ImagePromptValidator().validate(
        prompt,
        product_context=product_context,
        user_id=user_id,
        offer_id=offer_id,
    )


def _offer_description(context: dict | None) -> str:
    payload = context or {}
    product = payload.get("productContext") or {}
    offer = payload.get("offer") or {}
    return str(product.get("description") or offer.get("description") or "").strip()


def _with_offer_description(prompt: str, context: dict | None) -> str:
    description = _offer_description(context)
    if not description:
        return prompt
    if description in prompt:
        return prompt
    # Put the full offer description first so the image model must ground the scene in it.
    return normalize_image_prompt(
        f"Offer description (must be reflected in the scene): {description}\n\n{prompt}"
    )


async def generate_image_specification(
    *,
    offer_id: int,
    user_id: int,
    context: dict,
    brief: dict,
    concept: str,
    aspect: str,
    qr_safe: bool,
    run_id: int,
    item_id: int,
) -> dict:
    product = context.get("productContext") or {}
    offer_description = _offer_description(context)
    payload = {
        "description": offer_description,
        "mustReflectInScene": offer_description,
        "productContext": {
            "name": product.get("name") or "",
            "description": offer_description or (product.get("description") or ""),
            "category": product.get("category") or "",
            "geo": product.get("geo") or "",
            "verifiedFacts": [
                item
                for item in (product.get("verifiedFacts") or [])
                if str(item).strip() and not str(item).strip().startswith("http")
            ],
            "contextLimited": bool(product.get("contextLimited")),
        },
        "brief": {
            "promotedProduct": brief.get("promotedProduct") or product.get("name") or "",
            "targetAudience": brief.get("targetAudience"),
            "primaryCustomerNeed": brief.get("primaryCustomerNeed"),
            "mainValueProposition": brief.get("mainValueProposition"),
            "keyBenefits": brief.get("keyBenefits") or [],
            "verifiedProductFacts": brief.get("verifiedProductFacts") or [],
            "visualDirection": brief.get("visualDirection"),
            "toneOfVoice": brief.get("toneOfVoice"),
        },
        "concept": concept,
        "format": aspect,
        "qrSafe": qr_safe,
        "instruction": (
            "Build imagePrompt so the final image visually matches the full offer description, "
            "including product condition, audience, and setting. Do not replace specifics with a generic scene."
            if offer_description
            else "Build imagePrompt from available product facts only."
        ),
    }
    extra = _usage_meta(run_id=run_id, item_id=item_id, offer_id=offer_id)
    _, spec, _result = await run_structured(
        schema=promo_image_spec_schema(),
        schema_name="promo_image_spec",
        system_prompt=prompts.image_spec_system_prompt(qr_safe=qr_safe),
        user_prompt=json.dumps(payload, ensure_ascii=False),
        operation=Operation.PROMO_IMAGE_PROMPT_GENERATE,
        prompt_version=prompts.IMAGE_SPEC_V1,
        user_id=user_id,
        entity_id=str(offer_id),
        entity_type=EntityType.OFFER,
        payload_model=PromoImageSpecPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=True),
        extra_metadata=extra,
    )
    product = context.get("productContext")
    try:
        spec["imagePrompt"] = _validated_image_prompt(
            _with_offer_description(spec.get("imagePrompt") or "", context),
            product_context=product,
            user_id=user_id,
            offer_id=offer_id,
        )
        return spec
    except AppError as first_error:
        if first_error.code != "AI_INVALID_RESPONSE":
            raise
        compact_payload = {
            **payload,
            "previousPrompt": spec.get("imagePrompt") or "",
            "rewrite": "remove_affiliate_language",
        }
        _, compact, _result = await run_structured(
            schema=promo_image_spec_schema(),
            schema_name="promo_image_spec",
            system_prompt=prompts.image_spec_system_prompt(qr_safe=qr_safe, compact=True),
            user_prompt=json.dumps(compact_payload, ensure_ascii=False),
            operation=Operation.PROMO_IMAGE_PROMPT_GENERATE,
            prompt_version=prompts.IMAGE_SPEC_V1,
            user_id=user_id,
            entity_id=str(offer_id),
            entity_type=EntityType.OFFER,
            payload_model=PromoImageSpecPayload,
            model=promo_model(fast=True),
            reasoning_effort=promo_reasoning(heavy=False),
            extra_metadata=extra,
        )
        compact["imagePrompt"] = _validated_image_prompt(
            _with_offer_description(compact.get("imagePrompt") or "", context),
            product_context=product,
            user_id=user_id,
            offer_id=offer_id,
        )
        return compact


async def persist_slot_creative(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    slot: PromoSlot,
    payload: dict,
    generation_id: str,
) -> Creative:
    content = _content_from_slot_payload(slot, payload)
    return await CreativeService(db).create(
        offer=offer,
        user_id=user_id,
        partner_id=None,
        creative_type=slot.creative_type,
        source=CreativeSource.AI.value,
        status=CreativeStatus.DRAFT.value,
        title=slot.title,
        text_content=content,
        asset_id=None,
        language="ru",
        channel=slot.channel,
        image_format=slot.image_format,
        generation_id=generation_id,
        selected_variant=slot.id,
    )


async def create_slot_images(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    context: dict,
    brief: dict,
    slot: PromoSlot,
    generation_id: str,
    run_id: int,
    item_id: int,
    should_abort: Callable[[], Awaitable[bool]] | None = None,
    qr_tracking_link_id: int | None = None,
    qr_short_code: str | None = None,
) -> list[Creative]:
    created: list[Creative] = []
    count = max(1, slot.image_count)
    qr_safe = slot.kind == "qr_image"
    operation = Operation.PROMO_QR_IMAGE_GENERATE if qr_safe else Operation.PROMO_IMAGE_GENERATE
    extra = _usage_meta(run_id=run_id, item_id=item_id, offer_id=offer.id)
    concepts = brief.get("creativeConcepts") or []
    for index in range(count):
        if should_abort and await should_abort():
            await _discard_created_images(db, created)
            raise AppError("PROMO_CANCELLED", "Promo generation was cancelled", 409)
        concept = concepts[index] if index < len(concepts) else (concepts[0] if concepts else "")
        spec = await generate_image_specification(
            offer_id=offer.id,
            user_id=user_id,
            context=context,
            brief=brief,
            concept=concept,
            aspect=slot.aspect_ratio or "1:1",
            qr_safe=qr_safe,
            run_id=run_id,
            item_id=item_id,
        )
        if should_abort and await should_abort():
            await _discard_created_images(db, created)
            raise AppError("PROMO_CANCELLED", "Promo generation was cancelled", 409)
        _generation_id, result = await run_image(
            prompt=spec["imagePrompt"],
            aspect_ratio=slot.aspect_ratio or "1:1",
            image_format=slot.image_format or BannerFormat.SQUARE_1_1.value,
            operation=operation,
            prompt_version=prompts.IMAGE_SPEC_V1,
            user_id=user_id,
            entity_id=str(offer.id),
            entity_type=EntityType.OFFER,
            n=1,
            extra_metadata=extra,
        )
        if should_abort and await should_abort():
            await _discard_created_images(db, created)
            raise AppError("PROMO_CANCELLED", "Promo generation was cancelled", 409)
        image = result.images[0]
        title = slot.title if count == 1 else f"{slot.title} {index + 1}"
        layout = None
        if qr_safe:
            layout = dict(DEFAULT_QR_LAYOUT)
            if qr_tracking_link_id is not None:
                layout["tracking_link_id"] = qr_tracking_link_id
            if qr_short_code:
                layout["short_code"] = qr_short_code
        creative = await CreativeService(db).create(
            offer=offer,
            user_id=user_id,
            partner_id=None,
            creative_type=CreativeType.BANNER.value,
            source=CreativeSource.AI.value,
            status=CreativeStatus.DRAFT.value,
            title=title,
            text_content=layout,
            asset_id=None,
            language="ru",
            channel=slot.channel,
            image_format=slot.image_format,
            generation_id=generation_id,
            selected_variant=slot.id,
        )
        if should_abort and await should_abort():
            await db.delete(creative)
            await db.flush()
            await _discard_created_images(db, created)
            raise AppError("PROMO_CANCELLED", "Promo generation was cancelled", 409)
        asset = await AssetService(db).store_image(
            image.data,
            mime_type=image.mime_type,
            width=image.width,
            height=image.height,
            storage_key=promo_object_key(offer.id, creative.id, suffix=str(index + 1) if count > 1 else None),
        )
        if should_abort and await should_abort():
            await AssetService(db).delete_asset(asset)
            await db.delete(creative)
            await db.flush()
            await _discard_created_images(db, created)
            raise AppError("PROMO_CANCELLED", "Promo generation was cancelled", 409)
        creative.asset_id = asset.id
        await db.flush()
        created.append(creative)
        await db.commit()
        await db.refresh(creative)
        await db.refresh(offer)
    return created


async def _discard_created_images(db: AsyncSession, created: list[Creative]) -> None:
    for creative in created:
        asset_id = creative.asset_id
        if asset_id:
            asset = (await db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
            if asset:
                await AssetService(db).delete_asset(asset)
        await db.delete(creative)
    await db.flush()


async def regenerate_promo_material(
    db: AsyncSession,
    *,
    offer: Offer,
    creative: Creative,
    user_id: int,
) -> Creative:
    slot = creative.selected_variant or ""
    await db.commit()
    context, brief = await _brief_and_context(db, offer=offer, user_id=user_id)
    if creative.type == CreativeType.BANNER.value:
        return await _replace_promo_image(
            db,
            offer=offer,
            creative=creative,
            user_id=user_id,
            context=context,
            brief=brief,
        )
    meta = SLOTS.get(slot)
    if meta is not None:
        payload = await generate_slot_payload(
            offer_id=offer.id,
            user_id=user_id,
            context=context,
            brief=brief,
            slot=meta,
            run_id=0,
            item_id=0,
        )
        content = _content_from_slot_payload(meta, payload)
        return await CreativeService(db).update_content(
            creative,
            offer=offer,
            user_id=user_id,
            title=creative.title,
            text_content=content,
        )
    payload = await _generate_single_text(
        db,
        offer=offer,
        user_id=user_id,
        context=context,
        brief=brief,
        slot=slot or "universal_ad",
        creative_id=creative.id,
    )
    content = _text_content_from_single(slot, payload)
    return await CreativeService(db).update_content(
        creative,
        offer=offer,
        user_id=user_id,
        title=creative.title,
        text_content=content,
    )


async def _brief_and_context(db: AsyncSession, *, offer: Offer, user_id: int) -> tuple[dict, dict]:
    product = await _product(db, offer)
    context = await OfferPromotionContextBuilder().build(db, offer, product=product, language="ru")
    _, brief, _result = await run_structured(
        schema=promo_brief_schema(),
        schema_name="promo_brief",
        system_prompt=prompts.brief_system_prompt(),
        user_prompt=json.dumps(brief_user_payload(context), ensure_ascii=False),
        operation=Operation.PROMO_BRIEF_GENERATE,
        prompt_version=prompts.BRIEF_V1,
        user_id=user_id,
        entity_id=str(offer.id),
        entity_type=EntityType.OFFER,
        payload_model=PromoBriefPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=False),
    )
    brief = _sanitize_brief(brief, context)
    context = {**context, "brief": brief}
    return context, brief


async def _generate_kit_texts(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    context: dict,
    brief: dict,
) -> dict:
    payload = text_generation_payload(context, brief)
    _, data, _result = await run_structured(
        schema=promo_kit_texts_schema(),
        schema_name="promo_kit_texts",
        system_prompt=prompts.kit_texts_system_prompt(),
        user_prompt=json.dumps(payload, ensure_ascii=False),
        operation=Operation.PROMO_TEXT_GENERATE,
        prompt_version=prompts.KIT_TEXT_V1,
        user_id=user_id,
        entity_id=str(offer.id),
        entity_type=EntityType.OFFER,
        payload_model=PromoKitTextsPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=False),
    )
    assert_customer_facing_copy(data, product_context=context.get("productContext"))
    return data


async def _persist_kit_texts(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    texts: dict,
    generation_id: str,
) -> list[int]:
    service = CreativeService(db)
    created: list[int] = []
    for slot, meta in TEXT_SLOTS.items():
        content = _text_content_for_slot(slot, texts)
        if not content:
            continue
        creative = await service.create(
            offer=offer,
            user_id=user_id,
            partner_id=None,
            creative_type=meta["type"],
            source=CreativeSource.AI.value,
            status=CreativeStatus.DRAFT.value,
            title=meta["title"],
            text_content=content,
            asset_id=None,
            language="ru",
            channel=meta["channel"],
            image_format=None,
            generation_id=generation_id,
            selected_variant=slot,
        )
        created.append(creative.id)
    return created


async def _generate_single_text(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    context: dict,
    brief: dict,
    slot: str,
    creative_id: int,
) -> dict:
    payload = text_generation_payload(context, brief, slot)
    _, data, _result = await run_structured(
        schema=promo_single_text_schema(),
        schema_name="promo_single_text",
        system_prompt=prompts.single_text_system_prompt(slot),
        user_prompt=json.dumps(payload, ensure_ascii=False),
        operation=Operation.PROMO_TEXT_GENERATE,
        prompt_version=prompts.SINGLE_TEXT_V1,
        user_id=user_id,
        entity_id=str(creative_id),
        entity_type=EntityType.CREATIVE,
        payload_model=PromoSingleTextPayload,
        model=promo_model(),
        reasoning_effort=promo_reasoning(heavy=False),
    )
    assert_customer_facing_copy(data, product_context=context.get("productContext"))
    return data


async def _create_promo_image(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    context: dict,
    brief: dict,
    index: int,
    generation_id: str,
) -> Creative:
    concepts = brief.get("creativeConcepts") or []
    concept = concepts[index] if index < len(concepts) else (concepts[0] if concepts else "")
    spec = await generate_image_specification(
        offer_id=offer.id,
        user_id=user_id,
        context=context,
        brief=brief,
        concept=concept,
        aspect="1:1",
        qr_safe=False,
        run_id=0,
        item_id=0,
    )
    _generation_id, result = await run_image(
        prompt=spec["imagePrompt"],
        aspect_ratio="1:1",
        image_format=BannerFormat.SQUARE_1_1.value,
        operation=Operation.PROMO_IMAGE_GENERATE,
        prompt_version=prompts.IMAGE_SPEC_V1,
        user_id=user_id,
        entity_id=str(offer.id),
        entity_type=EntityType.OFFER,
        n=1,
    )
    image = result.images[0]
    creative = await CreativeService(db).create(
        offer=offer,
        user_id=user_id,
        partner_id=None,
        creative_type=CreativeType.BANNER.value,
        source=CreativeSource.AI.value,
        status=CreativeStatus.DRAFT.value,
        title="Промо-изображение 1:1",
        text_content=None,
        asset_id=None,
        language="ru",
        channel=CreativeChannel.GENERAL.value,
        image_format=BannerFormat.SQUARE_1_1.value,
        generation_id=generation_id,
        selected_variant="promo_image",
    )
    asset = await AssetService(db).store_image(
        image.data,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        storage_key=promo_object_key(offer.id, creative.id),
    )
    creative.asset_id = asset.id
    await db.flush()
    return creative


async def _replace_promo_image(
    db: AsyncSession,
    *,
    offer: Offer,
    creative: Creative,
    user_id: int,
    context: dict,
    brief: dict,
) -> Creative:
    concepts = brief.get("creativeConcepts") or []
    concept = concepts[0] if concepts else ""
    qr_safe = (creative.selected_variant or "") == "images_qr"
    aspect = BANNER_ASPECT.get(creative.format or "", "1:1")
    operation = Operation.PROMO_QR_IMAGE_GENERATE if qr_safe else Operation.PROMO_IMAGE_GENERATE
    spec = await generate_image_specification(
        offer_id=offer.id,
        user_id=user_id,
        context=context,
        brief=brief,
        concept=concept,
        aspect=aspect,
        qr_safe=qr_safe,
        run_id=0,
        item_id=0,
    )
    _generation_id, result = await run_image(
        prompt=spec["imagePrompt"],
        aspect_ratio=aspect,
        image_format=creative.format or BannerFormat.SQUARE_1_1.value,
        operation=operation,
        prompt_version=prompts.IMAGE_SPEC_V1,
        user_id=user_id,
        entity_id=str(creative.id),
        entity_type=EntityType.CREATIVE,
        n=1,
        extra_metadata=_usage_meta(run_id=0, item_id=0, offer_id=offer.id),
    )
    image = result.images[0]
    new_asset = await AssetService(db).store_image(
        image.data,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        storage_key=promo_object_key(offer.id, creative.id, suffix=uuid.uuid4().hex[:8]),
    )
    old_id = creative.asset_id
    creative.asset_id = new_asset.id
    await db.flush()
    if old_id:
        old = (await db.execute(select(Asset).where(Asset.id == old_id))).scalar_one_or_none()
        if old:
            await AssetService(db).delete_asset(old)
    return creative


def _content_from_slot_payload(slot: PromoSlot, payload: dict) -> dict:
    if slot.kind in {"yandex", "search_ads"}:
        headlines = [str(item).strip() for item in (payload.get("headlines") or []) if str(item).strip()]
        descriptions = [str(item).strip() for item in (payload.get("descriptions") or []) if str(item).strip()]
        return {
            "headline": headlines[0] if headlines else "",
            "body": "\n".join(headlines),
            "cta": "",
            "items": headlines,
            "descriptions": descriptions,
            "kind": slot.id,
        }
    if slot.kind == "meta":
        primary = [str(item).strip() for item in (payload.get("primaryTexts") or []) if str(item).strip()]
        headlines = [str(item).strip() for item in (payload.get("headlines") or []) if str(item).strip()]
        descriptions = [str(item).strip() for item in (payload.get("descriptions") or []) if str(item).strip()]
        return {
            "headline": headlines[0] if headlines else "",
            "body": "\n\n".join(primary),
            "cta": "",
            "items": headlines,
            "descriptions": descriptions,
            "primary_texts": primary,
            "kind": "meta_ads",
        }
    if slot.kind == "tiktok":
        hooks = [str(item).strip() for item in (payload.get("hooks") or []) if str(item).strip()]
        captions = [str(item).strip() for item in (payload.get("captions") or []) if str(item).strip()]
        ctas = [str(item).strip() for item in (payload.get("ctas") or []) if str(item).strip()]
        return {
            "headline": hooks[0] if hooks else "",
            "body": "\n\n".join(captions),
            "cta": ctas[0] if ctas else "",
            "items": hooks,
            "descriptions": captions,
            "hooks": hooks,
            "captions": captions,
            "ctas": ctas,
            "kind": "tiktok_ads",
        }
    if slot.kind == "social":
        return _text_content_for_slot(slot.id, {slot.id: payload.get("posts") or []}) or {
            "headline": "",
            "body": "",
            "cta": "",
            "hashtags": [],
        }
    return _text_content_from_single(slot.id, payload)


def _text_content_for_slot(slot: str, texts: dict) -> dict | None:
    if slot == "headlines":
        items = [str(item).strip() for item in (texts.get("headlines") or []) if str(item).strip()]
        if not items:
            return None
        return {"headline": items[0], "body": "\n".join(items), "cta": "", "items": items}
    if slot == "descriptions":
        items = [str(item).strip() for item in (texts.get("descriptions") or []) if str(item).strip()]
        if not items:
            return None
        return {"headline": items[0], "body": "\n".join(items), "cta": "", "items": items}
    if slot in {"telegram_posts", "vk_posts", "telegram", "vk_ads"}:
        posts = texts.get(slot) or []
        if not posts:
            return None
        first = posts[0] if isinstance(posts[0], dict) else {}
        bodies = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            parts = [post.get("headline") or "", post.get("body") or "", post.get("cta") or ""]
            bodies.append("\n".join(part for part in parts if part))
        return {
            "headline": first.get("headline") or "",
            "body": "\n\n".join(bodies),
            "cta": first.get("cta") or "",
            "hashtags": first.get("hashtags") or [],
            "variants": posts,
        }
    block = texts.get(slot) or {}
    if not isinstance(block, dict):
        return None
    if not (block.get("headline") or block.get("body")):
        return None
    return {
        "headline": block.get("headline") or "",
        "body": block.get("body") or "",
        "cta": block.get("cta") or "",
        "hashtags": block.get("hashtags") or [],
    }


def _text_content_from_single(slot: str, payload: dict) -> dict:
    items = payload.get("items") or []
    if slot in {"headlines", "descriptions"} and items:
        return {
            "headline": items[0],
            "body": "\n".join(items),
            "cta": payload.get("cta") or "",
            "items": items,
        }
    return {
        "headline": payload.get("headline") or "",
        "body": payload.get("body") or "",
        "cta": payload.get("cta") or "",
        "hashtags": payload.get("hashtags") or [],
        "items": items,
    }


async def _product(db: AsyncSession, offer: Offer) -> Product | None:
    if not offer.product_id:
        return None
    return (await db.execute(select(Product).where(Product.id == offer.product_id))).scalar_one_or_none()


def _sanitize_brief(brief: dict, snapshot: dict) -> dict:
    product = snapshot.get("productContext") or {}
    cleaned = dict(brief)
    cleaned["purpose"] = PURPOSE_CUSTOMER_ACQUISITION
    list_keys = ("keyBenefits", "verifiedProductFacts", "allowedClaims", "creativeConcepts", "restrictions", "prohibitedClaims")
    for key in list_keys:
        cleaned[key] = [
            item
            for item in (cleaned.get(key) or [])
            if not looks_like_affiliate_recruiting(item, product_context=product)
        ]
    for key in ("mainValueProposition", "primaryCustomerNeed", "targetAudience", "positioning", "visualDirection"):
        cleaned[key] = strip_affiliate_language(cleaned.get(key) or "", product_context=product)
    cta = cleaned.get("cta") or ""
    if looks_like_affiliate_recruiting(cta, product_context=product):
        cleaned["cta"] = "Узнать подробнее"
    if not (cleaned.get("promotedProduct") or "").strip():
        cleaned["promotedProduct"] = product.get("name") or ""
    concepts = [
        item
        for item in (cleaned.get("creativeConcepts") or [])
        if not looks_like_affiliate_recruiting(item, product_context=product)
    ]
    cleaned["creativeConcepts"] = concepts
    return cleaned


async def _reload_offer(db: AsyncSession, offer_id: int) -> Offer:
    offer = (await db.execute(select(Offer).where(Offer.id == offer_id))).scalar_one()
    return offer


def _error_code(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    if isinstance(exc, AiError):
        return getattr(exc, "code", "AI_UNAVAILABLE")
    return "AI_UNAVAILABLE"
