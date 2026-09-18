from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ids import parse_id
from app.core.permissions import get_session_data
from app.modules.finance.lookup.service import LegalEntityLookupService

router = APIRouter()


class SelectLegalEntityRequest(BaseModel):
    candidate_id: str = Field(min_length=8, max_length=2000)
    target_context: str = Field(pattern="^(business|partner)$")


@router.get("/search")
async def search_legal_entities(
    query: str = Query(min_length=1, max_length=200),
    context: str = Query(pattern="^(business|partner)$"),
    subject_type: str | None = Query(default=None),
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    return await LegalEntityLookupService(db).search(
        user_id=parse_id(session_data["user_id"]),
        query=query,
        context=context,
        subject_type=subject_type,
    )


@router.post("/select")
async def select_legal_entity(
    data: SelectLegalEntityRequest,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"]) if session_data.get("active_business_id") else None
    return await LegalEntityLookupService(db).select(
        user_id=parse_id(session_data["user_id"]),
        candidate_id=data.candidate_id,
        target_context=data.target_context,
        business_id=business_id,
    )
