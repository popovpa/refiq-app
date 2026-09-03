from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.core.ids import parse_id
from app.modules.ai.application.runner import run_structured
from app.modules.ai.capabilities import Operation
from app.modules.ai.context.offer_context import OfferAIContextBuilder
from app.modules.ai.dto import OfferRewritePayload
from app.modules.ai.offer_fields import REWRITE_FIELDS
from app.modules.ai.prompts import offer as prompts
from app.modules.ai.safety.operations import AiOperation, InputSource, rewrite_operation
from app.modules.ai.safety.output_guard import filter_allowed_fields, guard_output
from app.modules.ai.safety.pipeline import INVALID_OFFER_GUIDANCE_MESSAGE, evaluate_user_guidance
from app.modules.ai.safety.policy import get_operation_policy
from app.modules.ai.safety.trusted_prompt import build_structured_user_prompt, untrusted_block
from app.modules.ai.safety.verified_context import build_verified_context
from app.modules.ai.schemas import offer_rewrite_schema
from app.modules.offers.models import Offer
from app.modules.products.models import Product


def _validate_field(field: str) -> str:
    if field not in REWRITE_FIELDS:
        raise AppError("AI_FIELD_NOT_SUPPORTED", "This field cannot be rewritten with AI", 400)
    return field


async def rewrite_offer_field(
    db: AsyncSession | None,
    *,
    user_id: int,
    business_id: int | None,
    field: str,
    preset: str,
    offer_id: str | None = None,
    current_value: str | None = None,
    form_context: dict | None = None,
) -> dict:
    field = _validate_field(field)
    operation = rewrite_operation(field)
    policy = get_operation_policy(operation)
    entity_id = None
    offer_ref = None
    if offer_id:
        if db is None or business_id is None:
            raise AppError("AI_OFFER_REQUIRED", "Offer context is required", 400)
        offer = await _owned_offer(db, offer_id, business_id)
        product = await _product(db, offer)
        context = OfferAIContextBuilder().from_offer(offer, product)
        value = context.get(field) if current_value is None else current_value
        entity_id = str(offer.id)
        offer_ref = offer.id
    else:
        context = OfferAIContextBuilder().from_form(form_context or {})
        value = current_value if current_value is not None else context.get(field, "")

    verified = build_verified_context(field=field, current_value=str(value or ""), offer_context=context)
    evaluated = await evaluate_user_guidance(
        operation=operation,
        preset=preset,
        user_id=user_id,
        offer_id=offer_ref,
        message=INVALID_OFFER_GUIDANCE_MESSAGE,
    )
    generation_id, payload, _result = await run_structured(
        schema=offer_rewrite_schema(),
        schema_name="offer_field_rewrite",
        system_prompt=prompts.rewrite_system_prompt(operation),
        user_prompt=build_structured_user_prompt(
            operation=operation,
            trusted={
                "preset": evaluated.preset,
                "field": field,
                "trustedInstruction": evaluated.composed,
                "VERIFIED_CONTEXT": verified.as_prompt_dict(),
            },
            untrusted={
                "OFFER_DATA": untrusted_block(context, InputSource.OFFER_FIELD),
                "CURRENT_VALUE": untrusted_block(value, InputSource.OFFER_FIELD),
            },
            compat={
                "field": field,
                "instruction": evaluated.composed,
                "current_value": value,
                "offer": context,
            },
        ),
        operation=Operation.OFFER_FIELD_REWRITE,
        prompt_version=prompts.REWRITE_V1,
        user_id=user_id,
        entity_id=entity_id,
        payload_model=OfferRewritePayload,
    )
    guard_output(
        payload,
        operation=operation,
        user_id=user_id,
        offer_id=offer_ref,
        verified_context=verified,
        policy=policy,
        source_text=str(value or ""),
    )
    filtered = filter_allowed_fields({"value": payload["value"]}, operation)
    return {
        "generation_id": generation_id,
        "field": field,
        "value": filtered.get("value", payload["value"]),
    }


async def _owned_offer(db: AsyncSession, offer_id: str, business_id: int) -> Offer:
    offer = (
        await db.execute(select(Offer).where(Offer.id == parse_id(offer_id), Offer.business_id == business_id))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    return offer


async def _product(db: AsyncSession, offer: Offer) -> Product | None:
    if not offer.product_id:
        return None
    return (await db.execute(select(Product).where(Product.id == offer.product_id))).scalar_one_or_none()
