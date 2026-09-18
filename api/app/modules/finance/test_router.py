from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ProfileStatus
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import get_session_data
from app.modules.finance.audit import record_audit
from app.modules.finance.jobs import run_financial_jobs
from app.modules.finance.models import PartnerPayoutProfile
from app.modules.finance.providers.factory import get_payment_provider
from app.modules.finance.providers.test_provider import TestFinancialProvider

router = APIRouter()


def _ensure_test_mode() -> None:
    if settings.is_production or settings.FINANCIAL_TRANSACTIONS_ENABLED:
        raise ForbiddenError("Test financial API is disabled")


class SetOperationStatus(BaseModel):
    status: str


@router.post("/jobs/run")
async def run_jobs(session_data: dict = Depends(get_session_data)):
    _ensure_test_mode()
    return await run_financial_jobs()


@router.post("/operations/{provider_transaction_id}/status")
async def set_operation_status(
    provider_transaction_id: str,
    data: SetOperationStatus,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    _ensure_test_mode()
    provider = get_payment_provider(db)
    if not isinstance(provider, TestFinancialProvider):
        provider = TestFinancialProvider(db)
    result = await provider.set_status(provider_transaction_id, data.status)
    if not result.ok:
        raise NotFoundError("Test operation")
    await record_audit(
        db,
        action="test.operation_status",
        entity_type="test_financial_operation",
        entity_id=provider_transaction_id,
        actor_user_id=parse_id(session_data["user_id"]),
        new_status=data.status,
        system_actor="test",
    )
    return {"provider_transaction_id": provider_transaction_id, "status": result.provider_status}


@router.post("/payout-profiles/{profile_id}/verify")
async def verify_payout_profile(
    profile_id: str,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    _ensure_test_mode()
    profile = await db.get(PartnerPayoutProfile, parse_id(profile_id))
    if not profile:
        raise NotFoundError("PartnerPayoutProfile")
    profile.status = ProfileStatus.VERIFIED.value
    profile.verified_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="payout_profile.verified",
        entity_type="payout_profile",
        entity_id=profile.id,
        actor_user_id=parse_id(session_data["user_id"]),
        new_status=profile.status,
        system_actor="test",
    )
    return {"id": profile.id, "status": profile.status}
