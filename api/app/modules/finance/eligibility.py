from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, LegalVerificationStatus, PartnerStatus, ProfileStatus, TaxStatus
from app.modules.finance.legal import is_complete_for_type
from app.modules.finance.models import LegalEntity, PartnerPayoutProfile
from app.modules.partners.models import PartnerProfile


@dataclass(frozen=True)
class PayoutEligibility:
    eligible: bool
    reason_code: str | None
    reason_message: str | None

    def as_dict(self) -> dict:
        return {
            "eligible": self.eligible,
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
        }


class PartnerPayoutEligibilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_payout_eligibility(self, partner_id: int) -> PayoutEligibility:
        partner = await self.db.scalar(select(PartnerProfile).where(PartnerProfile.id == partner_id))
        if not partner:
            return PayoutEligibility(False, "LEGAL_ENTITY_MISSING", "Partner profile not found")
        if partner.status == PartnerStatus.SUSPENDED.value:
            return PayoutEligibility(False, "PARTNER_BLOCKED", "Partner is blocked")

        if not partner.legal_entity_id:
            return PayoutEligibility(False, "LEGAL_ENTITY_MISSING", "Legal entity is not filled in")
        entity = await self.db.scalar(select(LegalEntity).where(LegalEntity.id == partner.legal_entity_id))
        if not entity:
            return PayoutEligibility(False, "LEGAL_ENTITY_MISSING", "Legal entity is not filled in")
        if entity.verification_status == LegalVerificationStatus.BLOCKED.value:
            return PayoutEligibility(False, "PARTNER_BLOCKED", "Legal entity is blocked")
        if entity.verification_status != LegalVerificationStatus.VERIFIED.value:
            return PayoutEligibility(False, "LEGAL_ENTITY_NOT_VERIFIED", "Legal entity is not verified")
        if not is_complete_for_type(entity):
            return PayoutEligibility(False, "LEGAL_ENTITY_MISSING", "Legal entity data is incomplete")

        if entity.subject_type == LegalSubjectType.INDIVIDUAL.value:
            if entity.tax_status != TaxStatus.NPD.value:
                return PayoutEligibility(
                    False,
                    "UNSUPPORTED_PARTNER_TYPE",
                    "Ordinary individuals cannot receive payouts",
                )
        elif entity.subject_type not in {
            LegalSubjectType.SOLE_PROPRIETOR.value,
            LegalSubjectType.LEGAL_ENTITY.value,
        }:
            return PayoutEligibility(False, "UNSUPPORTED_PARTNER_TYPE", "Partner type cannot receive payouts")

        profile = await self.db.scalar(
            select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner_id)
        )
        if not profile:
            return PayoutEligibility(False, "PAYOUT_PROFILE_MISSING", "Payout details are not filled in")
        if profile.status == ProfileStatus.BLOCKED.value:
            return PayoutEligibility(False, "PAYOUT_PROFILE_NOT_VERIFIED", "Payout profile is blocked")
        if profile.status != ProfileStatus.VERIFIED.value:
            return PayoutEligibility(False, "PAYOUT_PROFILE_NOT_VERIFIED", "Payout details are not verified")
        if not _payment_details_valid(profile):
            return PayoutEligibility(False, "PAYMENT_DETAILS_INVALID", "Bank details are invalid")
        return PayoutEligibility(True, None, None)


def _payment_details_valid(profile: PartnerPayoutProfile) -> bool:
    method = (profile.payout_method or "bank_transfer").lower()
    if method in {"bank_transfer", "bank"}:
        account = (profile.bank_account or "").replace(" ", "")
        bik = (profile.bank_bik or "").replace(" ", "")
        return len(account) == 20 and account.isdigit() and len(bik) == 9 and bik.isdigit()
    if method in {"sbp", "card"}:
        return bool((profile.bank_account or "").strip())
    return False
