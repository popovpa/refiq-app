from __future__ import annotations

from app.modules.ai.application.runner import run_structured
from app.modules.ai.capabilities import Operation
from app.modules.ai.context.offer_context import OfferAIContextBuilder
from app.modules.ai.dto import OfferDraftPayload
from app.modules.ai.prompts import offer as prompts
from app.modules.ai.safety.operations import AiOperation, InputSource
from app.modules.ai.safety.output_guard import guard_output
from app.modules.ai.safety.pipeline import INVALID_OFFER_GUIDANCE_MESSAGE, evaluate_user_guidance, inspect_untrusted_text
from app.modules.ai.safety.trusted_prompt import build_structured_user_prompt, untrusted_block
from app.modules.ai.schemas import offer_draft_schema
from app.modules.ai.website.provider import load_website_context


async def generate_offer_draft(
    *,
    user_id: int,
    description: str,
    category: str | None = None,
    product_url: str | None = None,
) -> dict:
    evaluated = await evaluate_user_guidance(
        operation=AiOperation.GENERATE_OFFER,
        guidance=description,
        user_id=user_id,
        message=INVALID_OFFER_GUIDANCE_MESSAGE,
    )
    website_payload = None
    website_status = "skipped"
    image_url = None
    url = (product_url or "").strip() or None
    if url:
        website = await load_website_context(url)
        website_payload = website.to_prompt()
        website_status = website.status
        image_url = website.image_data_url
        if website_payload.get("status") == "ok":
            inspect_untrusted_text(
                " ".join(
                    str(website_payload.get(key) or "")
                    for key in ("title", "description", "h1", "main_text", "product_description")
                ),
                operation=AiOperation.GENERATE_OFFER,
                source=InputSource.LANDING_PAGE,
                user_id=user_id,
            )
    context = OfferAIContextBuilder().from_inputs(
        description=evaluated.guidance,
        category=category,
        product_url=url,
        website=website_payload,
    )
    generation_id, payload, _result = await run_structured(
        schema=offer_draft_schema(),
        schema_name="offer_draft",
        system_prompt=prompts.create_system_prompt(),
        user_prompt=build_structured_user_prompt(
            operation=AiOperation.GENERATE_OFFER,
            untrusted={
                "USER_GUIDANCE": untrusted_block(evaluated.guidance, InputSource.USER_GUIDANCE),
                "EXTERNAL_CONTENT": untrusted_block(website_payload, InputSource.LANDING_PAGE),
            },
            compat=context,
        ),
        operation=Operation.OFFER_CREATE_DRAFT,
        prompt_version=prompts.CREATE_V1,
        user_id=user_id,
        entity_id=None,
        payload_model=OfferDraftPayload,
    )
    guard_output(payload, operation=AiOperation.GENERATE_OFFER, user_id=user_id)
    if url and not (payload["draft"].get("product_url") or "").strip():
        payload["draft"]["product_url"] = url
    return {
        "generation_id": generation_id,
        "draft": payload["draft"],
        "recommendations": payload["recommendations"],
        "image_url": image_url,
        "website": {"status": website_status},
    }
