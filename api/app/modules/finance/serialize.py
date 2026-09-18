from __future__ import annotations

from datetime import datetime, timezone

from app.common.enums import ProfileStatus
from app.modules.finance.models import BusinessBillingProfile, PartnerPayoutProfile


def mask_account(value: str | None) -> str | None:
    if not value:
        return None
    digits = value.replace(" ", "")
    if len(digits) <= 4:
        return "•" * len(digits)
    return f"{'•' * (len(digits) - 4)}{digits[-4:]}"


def serialize_payout_profile(profile: PartnerPayoutProfile | None, *, owner: bool) -> dict | None:
    if profile is None:
        return None
    payload = {
        "id": profile.id,
        "partner_id": profile.partner_id,
        "legal_entity_id": profile.legal_entity_id,
        "provider": profile.provider,
        "payout_method": profile.payout_method,
        "bank_name": profile.bank_name,
        "status": profile.status,
        "verification_error": profile.verification_error,
        "verified_at": profile.verified_at.isoformat() if profile.verified_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
    if owner:
        payload.update(
            {
                "bank_account_masked": mask_account(profile.bank_account),
                "bank_bik_masked": mask_account(profile.bank_bik),
                "has_bank_account": bool(profile.bank_account),
                "has_bank_bik": bool(profile.bank_bik),
            }
        )
    return payload


def serialize_billing_profile(profile: BusinessBillingProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "business_id": profile.business_id,
        "legal_entity_id": profile.legal_entity_id,
        "provider": profile.provider,
        "billing_email": profile.billing_email,
        "status": profile.status,
        "auto_payout_enabled": bool(profile.auto_payout_enabled),
        "has_provider_customer": bool(profile.provider_customer_id),
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def payout_profile_status_from_details(profile: PartnerPayoutProfile) -> str:
    from app.modules.finance.eligibility import _payment_details_valid

    if profile.status == ProfileStatus.BLOCKED.value:
        return ProfileStatus.BLOCKED.value
    if _payment_details_valid(profile):
        return ProfileStatus.PENDING_VERIFICATION.value
    return ProfileStatus.INCOMPLETE.value
