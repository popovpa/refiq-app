from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.ids import parse_id
from app.core.permissions import get_session_data, require_business_role
from app.modules.ai.application.creative.generate import serialize_generation
from app.modules.ai.application.offer.edit_offer import propose_offer_edit
from app.modules.ai.application.offer.generate_offer_draft import generate_offer_draft
from app.modules.ai.application.offer.rewrite_offer_field import rewrite_offer_field
from app.modules.ai.lifecycle.service import AiGenerationService
from app.modules.ai.usage.service import AiUsageService

router = APIRouter()

FEEDBACK_OUTCOMES = {
    "ACCEPTED",
    "PARTIALLY_ACCEPTED",
    "REJECTED",
    "EDITED_AFTER_GENERATION",
    "GENERATED",
    "EDITED",
    "PUBLISHED",
}


class GenerateDraftRequest(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    category: str | None = None
    product_url: str | None = None


class EditOfferRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    context: dict | None = None


class RewriteFieldRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    value: str | None = None
    context: dict | None = None


class GenerationFeedbackRequest(BaseModel):
    outcome: str
    generated_fields_count: int | None = None
    accepted_fields_count: int | None = None
    modified_fields_count: int | None = None
    rejected_fields_count: int | None = None


@router.post("/offers/draft")
async def create_offer_draft(
    data: GenerateDraftRequest,
    session_data: dict = Depends(require_business_role),
):
    return await generate_offer_draft(
        user_id=parse_id(session_data["user_id"]),
        description=data.description,
        category=data.category,
        product_url=data.product_url,
    )


@router.post("/offers/fields/{field}/rewrite")
async def rewrite_form_field(
    field: str,
    data: RewriteFieldRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await rewrite_offer_field(
        db,
        user_id=parse_id(session_data["user_id"]),
        business_id=parse_id(session_data["active_business_id"]),
        field=field,
        instruction=data.instruction,
        current_value=data.value,
        form_context=data.context,
    )


@router.post("/offers/{offer_id}/edit")
async def edit_offer(
    offer_id: str,
    data: EditOfferRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await propose_offer_edit(
        db,
        user_id=parse_id(session_data["user_id"]),
        business_id=parse_id(session_data["active_business_id"]),
        offer_id=offer_id,
        instruction=data.instruction,
        form_context=data.context,
    )


@router.post("/offers/{offer_id}/fields/{field}/rewrite")
async def rewrite_existing_offer_field(
    offer_id: str,
    field: str,
    data: RewriteFieldRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await rewrite_offer_field(
        db,
        user_id=parse_id(session_data["user_id"]),
        business_id=parse_id(session_data["active_business_id"]),
        field=field,
        instruction=data.instruction,
        offer_id=offer_id,
        current_value=data.value,
        form_context=data.context,
    )


@router.get("/generations/{generation_id}")
async def get_generation(
    generation_id: str,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    row = await AiGenerationService(db).get(generation_id)
    if not row or row.user_id != parse_id(session_data["user_id"]):
        raise AppError("AI_GENERATION_NOT_FOUND", "Generation not found", 404)
    return await serialize_generation(row)


@router.post("/generations/{generation_id}/feedback")
async def record_generation_feedback(
    generation_id: str,
    data: GenerationFeedbackRequest,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    if data.outcome not in FEEDBACK_OUTCOMES:
        raise AppError("AI_FEEDBACK_INVALID", "Invalid feedback outcome", 400)
    usage = await AiUsageService(db).record_feedback(
        generation_id,
        user_id=parse_id(session_data["user_id"]),
        outcome=data.outcome,
        generated_fields_count=data.generated_fields_count,
        accepted_fields_count=data.accepted_fields_count,
        modified_fields_count=data.modified_fields_count,
        rejected_fields_count=data.rejected_fields_count,
    )
    return {
        "generation_id": usage.generation_id,
        "outcome": usage.feedback_outcome,
    }
