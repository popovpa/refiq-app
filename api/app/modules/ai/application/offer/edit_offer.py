from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ids import parse_id
from app.modules.ai.application.offer.values import (
    instruction_allows_business_rules,
    parse_change_value,
    serialize_value,
    values_equal,
)
from app.modules.ai.application.runner import run_structured
from app.modules.ai.capabilities import Operation
from app.modules.ai.context.offer_context import OfferAIContextBuilder
from app.modules.ai.dto import OfferEditPayload
from app.modules.ai.offer_fields import (
    ALLOWED_PATCH_FIELDS,
    BUSINESS_RULE_FIELDS,
    TECHNICAL_FIELDS,
)
from app.modules.ai.prompts import offer as prompts
from app.modules.ai.safety.operations import AiOperation, InputSource
from app.modules.ai.safety.output_guard import guard_output
from app.modules.ai.safety.pipeline import INVALID_OFFER_GUIDANCE_MESSAGE, evaluate_user_guidance
from app.modules.ai.safety.trusted_prompt import build_structured_user_prompt, untrusted_block
from app.modules.ai.schemas import offer_edit_schema
from app.modules.offers.models import Offer
from app.modules.products.models import Product


async def propose_offer_edit(
    db: AsyncSession,
    *,
    user_id: int,
    business_id: int,
    offer_id: str,
    instruction: str | None = None,
    guidance: str | None = None,
    preset: str | None = None,
    form_context: dict | None = None,
) -> dict:
    offer = await _owned_offer(db, offer_id, business_id)
    evaluated = await evaluate_user_guidance(
        operation=AiOperation.EDIT_OFFER,
        instruction=instruction,
        guidance=guidance,
        preset=preset,
        user_id=user_id,
        offer_id=offer.id,
        message=INVALID_OFFER_GUIDANCE_MESSAGE,
    )
    product = await _product(db, offer)
    context = OfferAIContextBuilder().from_offer(offer, product)
    if form_context:
        overlay = {
            key: value
            for key, value in OfferAIContextBuilder().from_form(form_context).items()
            if value is not None
        }
        context = {**context, **overlay}
    generation_id, payload, _result = await run_structured(
        schema=offer_edit_schema(),
        schema_name="offer_edit",
        system_prompt=prompts.edit_system_prompt(),
        user_prompt=build_structured_user_prompt(
            operation=AiOperation.EDIT_OFFER,
            trusted={"preset": evaluated.preset},
            untrusted={
                "USER_GUIDANCE": untrusted_block(evaluated.guidance, InputSource.USER_GUIDANCE),
                "OFFER_DATA": untrusted_block(context, InputSource.OFFER_FIELD),
            },
            compat={"instruction": evaluated.composed, "offer": context},
        ),
        operation=Operation.OFFER_EDIT,
        prompt_version=prompts.EDIT_V1,
        user_id=user_id,
        entity_id=str(offer.id),
        payload_model=OfferEditPayload,
    )
    guard_output(payload, operation=AiOperation.EDIT_OFFER, user_id=user_id, offer_id=offer.id)
    allow_rules = instruction_allows_business_rules(evaluated.guidance)
    changes = []
    seen: set[str] = set()
    for raw in payload["changes"]:
        field = raw["field"]
        if field in seen or field in TECHNICAL_FIELDS or field not in ALLOWED_PATCH_FIELDS:
            continue
        if field in BUSINESS_RULE_FIELDS and not allow_rules:
            continue
        new_value = parse_change_value(field, raw["new_value"])
        old_value = serialize_value(context.get(field))
        if values_equal(old_value, new_value):
            continue
        seen.add(field)
        kind = "recommendation" if field in BUSINESS_RULE_FIELDS else "content"
        changes.append(
            {
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "reason": (raw.get("reason") or "").strip(),
                "kind": kind,
            }
        )
    return {"generation_id": generation_id, "changes": changes}


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
