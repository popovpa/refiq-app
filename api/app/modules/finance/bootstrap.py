from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, LegalVerificationStatus, ProfileStatus, TaxStatus, TermsContext
from app.modules.businesses.models import Business
from app.modules.finance.billing import ensure_billing_profile, start_business_subscription
from app.modules.finance.models import LegalEntity, PartnerPayoutProfile
from app.modules.partners.models import PartnerProfile


async def ensure_business_legal_entity(db: AsyncSession, business: Business) -> LegalEntity:
    if business.legal_entity_id:
        entity = await db.get(LegalEntity, business.legal_entity_id)
        if entity:
            await ensure_billing_profile(db, business)
            await start_business_subscription(db, business)
            return entity
    entity = LegalEntity(
        subject_type=LegalSubjectType.LEGAL_ENTITY.value,
        tax_status=TaxStatus.UNKNOWN.value,
        country=(business.country or "RU").upper(),
        legal_name=business.legal_name or business.name,
        verification_status=LegalVerificationStatus.DRAFT.value,
    )
    db.add(entity)
    await db.flush()
    business.legal_entity_id = entity.id
    await ensure_billing_profile(db, business)
    await start_business_subscription(db, business)
    return entity


async def ensure_partner_legal_entity(db: AsyncSession, partner: PartnerProfile) -> LegalEntity:
    if partner.legal_entity_id:
        entity = await db.get(LegalEntity, partner.legal_entity_id)
        if entity:
            await ensure_payout_profile(db, partner)
            return entity
    entity = LegalEntity(
        subject_type=LegalSubjectType.INDIVIDUAL.value,
        tax_status=TaxStatus.UNKNOWN.value,
        country="RU",
        legal_name=partner.display_name,
        verification_status=LegalVerificationStatus.DRAFT.value,
    )
    db.add(entity)
    await db.flush()
    partner.legal_entity_id = entity.id
    await ensure_payout_profile(db, partner)
    return entity


async def ensure_payout_profile(db: AsyncSession, partner: PartnerProfile) -> PartnerPayoutProfile:
    from sqlalchemy import select

    profile = await db.scalar(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner.id))
    if profile:
        if partner.legal_entity_id and profile.legal_entity_id != partner.legal_entity_id:
            profile.legal_entity_id = partner.legal_entity_id
        return profile
    profile = PartnerPayoutProfile(
        partner_id=partner.id,
        legal_entity_id=partner.legal_entity_id,
        provider="TBANK",
        payout_method="bank_transfer",
        status=ProfileStatus.INCOMPLETE.value,
    )
    db.add(profile)
    await db.flush()
    return profile


def terms_context_for_role(role: str) -> str:
    return TermsContext.BUSINESS.value if role == "business" else TermsContext.PARTNER.value
