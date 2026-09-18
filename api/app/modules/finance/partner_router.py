from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ProfileStatus, TermsContext
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.ids import parse_id
from app.modules.commissions.models import Commission
from app.modules.finance.audit import record_audit
from app.modules.finance.bootstrap import ensure_partner_legal_entity, ensure_payout_profile
from app.modules.finance.commission import earnings_breakdown
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.legal import LegalEntityUpdate, serialize_legal_entity, validate_partner_legal_combination
from app.modules.finance.models import LegalEntity
from app.modules.finance.verification import LegalEntityVerificationService
from app.modules.finance.money import as_money
from app.modules.finance.permissions import require_partner_profile
from app.modules.finance.payouts import serialize_payout
from app.modules.finance.serialize import payout_profile_status_from_details, serialize_payout_profile
from app.modules.finance.terms import record_terms_acceptance
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout

router = APIRouter()


class PayoutProfileUpdate(BaseModel):
    payout_method: str | None = Field(default=None, max_length=40)
    bank_account: str | None = Field(default=None, max_length=32)
    bank_bik: str | None = Field(default=None, max_length=12)
    bank_name: str | None = Field(default=None, max_length=255)


class TermsAcceptRequest(BaseModel):
    document_type: str = "platform_terms"
    document_version: str = "2026-09-01"


def _mode_payload() -> dict:
    return {
        "financial_mode": settings.financial_mode_label,
        "financial_transactions_enabled": settings.FINANCIAL_TRANSACTIONS_ENABLED,
        "live": settings.live_financial_transactions_allowed,
    }


async def _partner(session_data: dict, db: AsyncSession) -> PartnerProfile:
    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.id == session_data["_partner_id"]))
    if not partner:
        raise NotFoundError("Partner profile")
    await ensure_partner_legal_entity(db, partner)
    return partner


@router.get("/legal-entity")
async def get_legal_entity(
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    entity = await db.get(LegalEntity, partner.legal_entity_id) if partner.legal_entity_id else None
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {
        "legal_entity": serialize_legal_entity(entity),
        "payout_eligibility": eligibility.as_dict(),
        **_mode_payload(),
    }


@router.patch("/legal-entity")
async def patch_legal_entity(
    data: LegalEntityUpdate,
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    if not partner.legal_entity_id:
        raise NotFoundError("LegalEntity")
    dumped = data.model_dump(exclude_unset=True)
    submit = bool(dumped.pop("submit", False))
    current = await db.get(LegalEntity, partner.legal_entity_id)
    if not current:
        raise NotFoundError("LegalEntity")
    validate_partner_legal_combination(
        dumped.get("subject_type", current.subject_type),
        dumped.get("tax_status", current.tax_status),
        submit=submit,
    )
    entity = await LegalEntityVerificationService(db).apply_user_update(
        partner.legal_entity_id,
        dumped,
        submit=submit,
        actor_user_id=parse_id(session_data["user_id"]),
    )
    await db.refresh(entity)
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {"legal_entity": serialize_legal_entity(entity), "payout_eligibility": eligibility.as_dict()}


@router.get("/payout-profile")
async def get_payout_profile(
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    profile = await ensure_payout_profile(db, partner)
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {
        "payout_profile": serialize_payout_profile(profile, owner=True),
        "payout_eligibility": eligibility.as_dict(),
        **_mode_payload(),
    }


@router.patch("/payout-profile")
async def patch_payout_profile(
    data: PayoutProfileUpdate,
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    profile = await ensure_payout_profile(db, partner)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(profile, key, value)
    profile.legal_entity_id = partner.legal_entity_id
    profile.status = payout_profile_status_from_details(profile)
    if profile.status == ProfileStatus.PENDING_VERIFICATION.value and not settings.live_financial_transactions_allowed:
        profile.status = ProfileStatus.VERIFIED.value
        profile.verified_at = datetime.now(timezone.utc)
        profile.verification_error = None
    await record_audit(
        db,
        action="payout_profile.updated",
        entity_type="payout_profile",
        entity_id=profile.id,
        actor_user_id=parse_id(session_data["user_id"]),
        new_status=profile.status,
    )
    await db.refresh(profile)
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {
        "payout_profile": serialize_payout_profile(profile, owner=True),
        "payout_eligibility": eligibility.as_dict(),
    }


@router.get("/earnings")
async def get_earnings(
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    totals = await earnings_breakdown(db, partner_id=partner.id)
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {**totals, "payout_eligibility": eligibility.as_dict(), **_mode_payload()}


@router.get("/commissions")
async def list_commissions(
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    rows = (
        await db.execute(
            select(Commission).where(Commission.partner_id == partner.id).order_by(Commission.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": item.id,
                "conversion_id": item.conversion_id,
                "offer_id": item.offer_id,
                "amount": float(as_money(item.amount)),
                "currency": item.currency,
                "status": item.status,
                "hold_period_days": item.hold_period_days,
                "available_at": item.available_at.isoformat() if item.available_at else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows
        ],
        **_mode_payload(),
    }


@router.get("/payouts")
async def list_payouts(
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    totals = await earnings_breakdown(db, partner_id=partner.id)
    rows = (
        await db.execute(
            select(Payout).where(Payout.partner_id == partner.id).order_by(Payout.created_at.desc()).limit(50)
        )
    ).scalars().all()
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    return {
        "pending": totals["pending"],
        "hold": totals["hold"],
        "available": totals["available"],
        "available_amount": totals["available"],
        "payout_pending": totals["payout_pending"],
        "paid": totals["paid"],
        "payouts": [serialize_payout(item) for item in rows],
        "payout_eligibility": eligibility.as_dict(),
        **_mode_payload(),
    }


@router.post("/terms/accept")
async def accept_partner_terms(
    data: TermsAcceptRequest,
    request: Request,
    session_data: dict = Depends(require_partner_profile),
    db: AsyncSession = Depends(get_db),
):
    partner = await _partner(session_data, db)
    item = await record_terms_acceptance(
        db,
        user_id=parse_id(session_data["user_id"]),
        context=TermsContext.PARTNER.value,
        document_type=data.document_type,
        document_version=data.document_version,
        legal_entity_id=partner.legal_entity_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"accepted_at": item.accepted_at.isoformat(), "document_version": item.document_version}
