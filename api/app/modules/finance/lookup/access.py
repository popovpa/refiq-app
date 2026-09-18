from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, MembershipStatus
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.finance.models import LegalEntity
from app.modules.partners.models import PartnerProfile


async def user_accessible_legal_entities(db: AsyncSession, user_id: int) -> list[LegalEntity]:
    ids = await user_accessible_legal_entity_ids(db, user_id)
    if not ids:
        return []
    rows = (await db.execute(select(LegalEntity).where(LegalEntity.id.in_(ids)))).scalars().all()
    return list(rows)


async def user_accessible_legal_entity_ids(db: AsyncSession, user_id: int) -> set[int]:
    ids: set[int] = set()
    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.user_id == user_id))
    if partner and partner.legal_entity_id:
        ids.add(partner.legal_entity_id)
    memberships = (
        await db.execute(
            select(BusinessMembership.business_id).where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.status == MembershipStatus.ACTIVE.value,
            )
        )
    ).scalars().all()
    if memberships:
        businesses = (
            await db.execute(select(Business).where(Business.id.in_(list(memberships))))
        ).scalars().all()
        for business in businesses:
            if business.legal_entity_id:
                ids.add(business.legal_entity_id)
    return ids


async def usage_labels_for_user(db: AsyncSession, user_id: int, legal_entity_id: int) -> list[str]:
    labels: list[str] = []
    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.user_id == user_id))
    if partner and partner.legal_entity_id == legal_entity_id:
        labels.append("partner")
    memberships = (
        await db.execute(
            select(Business.id, Business.legal_entity_id)
            .join(BusinessMembership, BusinessMembership.business_id == Business.id)
            .where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.status == MembershipStatus.ACTIVE.value,
                Business.legal_entity_id == legal_entity_id,
            )
        )
    ).all()
    if memberships:
        labels.append("business")
    return labels


def context_allows_subject(context: str, subject_type: str) -> bool:
    if context == "business":
        return subject_type in {
            LegalSubjectType.LEGAL_ENTITY.value,
            LegalSubjectType.SOLE_PROPRIETOR.value,
        }
    return subject_type in {
        LegalSubjectType.LEGAL_ENTITY.value,
        LegalSubjectType.SOLE_PROPRIETOR.value,
        LegalSubjectType.INDIVIDUAL.value,
    }


def normalize_inn(value: str | None) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits or None
