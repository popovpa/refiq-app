from __future__ import annotations

import json

from app.modules.ai.application.runner import run_structured
from app.modules.ai.capabilities import Operation
from app.modules.ai.context.offer_context import OfferAIContextBuilder
from app.modules.ai.dto import OfferDraftPayload
from app.modules.ai.prompts import offer as prompts
from app.modules.ai.schemas import offer_draft_schema
from app.modules.ai.website.provider import load_website_context


async def generate_offer_draft(
    *,
    user_id: int,
    description: str,
    category: str | None = None,
    product_url: str | None = None,
) -> dict:
    website_payload = None
    website_status = "skipped"
    image_url = None
    url = (product_url or "").strip() or None
    if url:
        website = await load_website_context(url)
        website_payload = website.to_prompt()
        website_status = website.status
        image_url = website.image_data_url
    context = OfferAIContextBuilder().from_inputs(
        description=description,
        category=category,
        product_url=url,
        website=website_payload,
    )
    generation_id, payload, _result = await run_structured(
        schema=offer_draft_schema(),
        schema_name="offer_draft",
        system_prompt=prompts.create_system_prompt(),
        user_prompt=json.dumps(context, ensure_ascii=False),
        operation=Operation.OFFER_CREATE_DRAFT,
        prompt_version=prompts.CREATE_V1,
        user_id=user_id,
        entity_id=None,
        payload_model=OfferDraftPayload,
    )
    if url and not (payload["draft"].get("product_url") or "").strip():
        payload["draft"]["product_url"] = url
    return {
        "generation_id": generation_id,
        "draft": payload["draft"],
        "recommendations": payload["recommendations"],
        "image_url": image_url,
        "website": {"status": website_status},
    }
