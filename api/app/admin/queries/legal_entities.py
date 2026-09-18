from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.models import AdminUser
from app.admin.queries.catalog import _offset_page
from app.admin.queries.common import iso
from app.common.enums import LegalVerificationStatus
from app.core.exceptions import NotFoundError
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.finance.legal import legal_entity_full_name
from app.modules.finance.models import LegalEntity, LegalEntityVerificationAttempt
from app.modules.partners.models import PartnerProfile
from app.modules.users.models import User

_STATUS_ORDER = case(
    (LegalEntity.verification_status == LegalVerificationStatus.PENDING_VERIFICATION.value, 0),
    (LegalEntity.verification_status == LegalVerificationStatus.REVIEW_REQUIRED.value, 1),
    (LegalEntity.verification_status == LegalVerificationStatus.REJECTED.value, 2),
    (LegalEntity.verification_status == LegalVerificationStatus.VERIFIED.value, 3),
    (LegalEntity.verification_status == LegalVerificationStatus.BLOCKED.value, 4),
    else_=5,
)


def _display_name(entity: LegalEntity) -> str | None:
    return entity.legal_name or legal_entity_full_name(entity)


def _serialize_entity(entity: LegalEntity, owners: dict) -> dict:
    owner = owners.get(entity.id) or {}
    return {
        "id": entity.id,
        "subject_type": entity.subject_type,
        "tax_status": entity.tax_status,
        "country": entity.country,
        "legal_name": entity.legal_name,
        "full_name": legal_entity_full_name(entity),
        "display_name": _display_name(entity),
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "middle_name": entity.middle_name,
        "inn": entity.inn,
        "ogrn": entity.ogrn,
        "ogrnip": entity.ogrnip,
        "legal_address": entity.legal_address,
        "verification_status": entity.verification_status,
        "verification_source": entity.verification_source,
        "verification_reason": entity.verification_reason,
        "verification_reason_code": entity.verification_reason_code,
        "verified_at": iso(entity.verified_at),
        "verified_by_admin_id": entity.verified_by_admin_id,
        "created_at": iso(entity.created_at),
        "updated_at": iso(entity.updated_at),
        **owner,
    }


async def _owners_for(db: AsyncSession, entity_ids: list[int]) -> dict[int, dict]:
    if not entity_ids:
        return {}
    owners: dict[int, dict] = {
        entity_id: {
            "owner_type": None,
            "business_id": None,
            "business_name": None,
            "partner_id": None,
            "partner_name": None,
            "owner_email": None,
            "owner_user_id": None,
        }
        for entity_id in entity_ids
    }

    businesses = (
        await db.execute(select(Business).where(Business.legal_entity_id.in_(entity_ids)))
    ).scalars().all()
    business_ids = [item.id for item in businesses]
    owner_emails: dict[int, tuple[int, str]] = {}
    if business_ids:
        rows = (
            await db.execute(
                select(BusinessMembership.business_id, User.id, User.email)
                .join(User, User.id == BusinessMembership.user_id)
                .where(
                    BusinessMembership.business_id.in_(business_ids),
                    BusinessMembership.permission_role == "owner",
                )
            )
        ).all()
        for business_id, user_id, email in rows:
            owner_emails.setdefault(business_id, (user_id, email))
    for business in businesses:
        slot = owners[business.legal_entity_id]
        slot["business_id"] = business.id
        slot["business_name"] = business.name
        owner = owner_emails.get(business.id)
        if owner:
            slot["owner_user_id"] = owner[0]
            slot["owner_email"] = owner[1]

    partners = (
        await db.execute(
            select(PartnerProfile, User.email)
            .join(User, User.id == PartnerProfile.user_id)
            .where(PartnerProfile.legal_entity_id.in_(entity_ids))
        )
    ).all()
    for partner, email in partners:
        slot = owners[partner.legal_entity_id]
        slot["partner_id"] = partner.id
        slot["partner_name"] = partner.display_name
        if not slot["owner_email"]:
            slot["owner_email"] = email
            slot["owner_user_id"] = partner.user_id

    for slot in owners.values():
        if slot["business_id"] and slot["partner_id"]:
            slot["owner_type"] = "shared"
        elif slot["business_id"]:
            slot["owner_type"] = "business"
        elif slot["partner_id"]:
            slot["owner_type"] = "partner"
        else:
            slot["owner_type"] = None
    return owners


async def list_legal_entities(
    db: AsyncSession,
    *,
    status: str | None = None,
    owner_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    stmt = select(LegalEntity)
    count_stmt = select(func.count(LegalEntity.id))
    filters = []
    if status:
        filters.append(LegalEntity.verification_status == status)
    if owner_type == "business":
        filters.append(
            LegalEntity.id.in_(select(Business.legal_entity_id).where(Business.legal_entity_id.is_not(None)))
        )
    elif owner_type == "partner":
        filters.append(
            LegalEntity.id.in_(
                select(PartnerProfile.legal_entity_id).where(PartnerProfile.legal_entity_id.is_not(None))
            )
        )
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    rows = (
        (
            await db.execute(
                stmt.order_by(_STATUS_ORDER, LegalEntity.updated_at.desc(), LegalEntity.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )
    owners = await _owners_for(db, [item.id for item in rows])
    return _offset_page(
        [_serialize_entity(item, owners) for item in rows],
        total,
        page,
        per_page,
    )


async def get_legal_entity(db: AsyncSession, legal_entity_id: int) -> dict:
    entity = await db.get(LegalEntity, legal_entity_id)
    if not entity:
        raise NotFoundError("LegalEntity")
    await db.refresh(entity)
    owners = await _owners_for(db, [entity.id])
    attempts = (
        (
            await db.execute(
                select(LegalEntityVerificationAttempt, AdminUser.email)
                .outerjoin(AdminUser, AdminUser.id == LegalEntityVerificationAttempt.actor_admin_id)
                .where(LegalEntityVerificationAttempt.legal_entity_id == entity.id)
                .order_by(
                    LegalEntityVerificationAttempt.requested_at.desc(),
                    LegalEntityVerificationAttempt.id.desc(),
                )
            )
        )
        .all()
    )
    payload = _serialize_entity(entity, owners)
    payload["attempts"] = [
        {
            "id": attempt.id,
            "provider": attempt.provider,
            "status": attempt.status,
            "actor_admin_id": attempt.actor_admin_id,
            "actor_admin_email": email,
            "actor_user_id": attempt.actor_user_id,
            "reason_code": attempt.reason_code,
            "public_reason": attempt.public_reason,
            "comment": attempt.comment,
            "requested_at": iso(attempt.requested_at),
            "completed_at": iso(attempt.completed_at),
            "provider_request_id": attempt.provider_request_id,
        }
        for attempt, email in attempts
    ]
    if entity.verified_by_admin_id:
        admin = await db.get(AdminUser, entity.verified_by_admin_id)
        payload["verified_by_admin_email"] = admin.email if admin else None
    else:
        payload["verified_by_admin_email"] = None
    return payload
