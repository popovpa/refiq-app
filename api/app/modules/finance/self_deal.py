from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import parse_id
from app.modules.businesses.models import Business
from app.modules.finance.audit import record_audit
from app.modules.finance.errors import fin_error
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.promotion.ownership import user_owned_business_ids

SAME_USER_BUSINESS_MEMBER = "SAME_USER_BUSINESS_MEMBER"
SAME_LEGAL_ENTITY = "SAME_LEGAL_ENTITY"
OWN_BUSINESS_OFFER = "OWN_BUSINESS_OFFER"
SELF_PROMOTION_FORBIDDEN = "SELF_PROMOTION_FORBIDDEN"
COMMISSION_SELF_DEAL_FORBIDDEN = "COMMISSION_SELF_DEAL_FORBIDDEN"
PAYOUT_SELF_DEAL_FORBIDDEN = "PAYOUT_SELF_DEAL_FORBIDDEN"
FIN_SELF_DEAL_FORBIDDEN = "FIN_SELF_DEAL_FORBIDDEN"
SELF_PROMOTION_INVALID = "SELF_PROMOTION_INVALID"

_MESSAGES = {
    SAME_USER_BUSINESS_MEMBER: "Собственный оффер продвигается через бизнес-пространство, без партнёрского доступа.",
    OWN_BUSINESS_OFFER: "Собственный оффер продвигается через бизнес-пространство, без партнёрского доступа.",
    SAME_LEGAL_ENTITY: "Нельзя продвигать оффер своей юридической организации как партнёр.",
    SELF_PROMOTION_FORBIDDEN: "Партнёр не может получать комиссию за оффер собственного бизнеса.",
}


@dataclass(frozen=True)
class SelfDealDecision:
    allowed: bool
    reason_code: str | None = None
    message: str | None = None
    partner_id: int | None = None
    partner_user_id: int | None = None
    business_id: int | None = None
    offer_id: int | None = None
    business_legal_entity_id: int | None = None
    partner_legal_entity_id: int | None = None

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "message": self.message,
        }


def _forbidden(*, reason_code: str, **ids) -> SelfDealDecision:
    return SelfDealDecision(
        allowed=False,
        reason_code=reason_code,
        message=_MESSAGES.get(reason_code, _MESSAGES[SELF_PROMOTION_FORBIDDEN]),
        **ids,
    )


async def check_self_deal(
    db: AsyncSession,
    *,
    partner_id: int,
    offer: Offer | None = None,
    business_id: int | None = None,
    user_id: str | int | None = None,
) -> SelfDealDecision:
    """Domain guard: Partner cannot earn affiliate commission on a Business they belong to
    or share a LegalEntity with. Does not use active_role.
    """
    resolved_business_id = offer.business_id if offer is not None else business_id
    ids = {
        "partner_id": partner_id,
        "business_id": resolved_business_id,
        "offer_id": offer.id if offer is not None else None,
    }
    if resolved_business_id is None:
        return SelfDealDecision(allowed=True, **ids)

    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.id == partner_id))
    if not partner:
        return SelfDealDecision(allowed=True, **ids)
    ids["partner_user_id"] = partner.user_id
    ids["partner_legal_entity_id"] = partner.legal_entity_id

    business = await db.scalar(select(Business).where(Business.id == resolved_business_id))
    if not business:
        return SelfDealDecision(allowed=True, **ids)
    ids["business_legal_entity_id"] = business.legal_entity_id

    member_business_ids = await user_owned_business_ids(db, partner.user_id)
    if resolved_business_id in member_business_ids:
        reason = OWN_BUSINESS_OFFER if offer is not None else SAME_USER_BUSINESS_MEMBER
        return _forbidden(reason_code=reason, **ids)

    if user_id is not None:
        acting_id = parse_id(user_id)
        if acting_id != partner.user_id:
            acting_ids = await user_owned_business_ids(db, acting_id)
            if resolved_business_id in acting_ids:
                return _forbidden(reason_code=SAME_USER_BUSINESS_MEMBER, **ids)

    if (
        business.legal_entity_id
        and partner.legal_entity_id
        and business.legal_entity_id == partner.legal_entity_id
    ):
        return _forbidden(reason_code=SAME_LEGAL_ENTITY, **ids)

    return SelfDealDecision(allowed=True, **ids)


async def record_self_promotion_blocked(
    db: AsyncSession,
    decision: SelfDealDecision,
    *,
    actor_user_id: int | None = None,
    system_actor: str | None = None,
    extra: dict | None = None,
) -> None:
    metadata = {
        "business_id": decision.business_id,
        "partner_id": decision.partner_id,
        "offer_id": decision.offer_id,
        "partner_user_id": decision.partner_user_id,
        "business_legal_entity_id": decision.business_legal_entity_id,
        "partner_legal_entity_id": decision.partner_legal_entity_id,
        **(extra or {}),
    }
    await record_audit(
        db,
        action="SELF_PROMOTION_BLOCKED",
        entity_type="partner_profile",
        entity_id=decision.partner_id or 0,
        actor_user_id=actor_user_id,
        system_actor=system_actor or ("system" if actor_user_id is None else None),
        reason=decision.reason_code,
        metadata=metadata,
    )


async def assert_not_self_deal(
    db: AsyncSession,
    *,
    offer: Offer,
    partner_id: int,
    user_id: str | int | None = None,
    actor_user_id: int | None = None,
    audit: bool = True,
) -> SelfDealDecision:
    decision = await check_self_deal(db, offer=offer, partner_id=partner_id, user_id=user_id)
    if decision.allowed:
        return decision
    if audit:
        await record_self_promotion_blocked(
            db,
            decision,
            actor_user_id=actor_user_id or (parse_id(user_id) if user_id is not None else None),
        )
    raise fin_error(
        decision.reason_code or FIN_SELF_DEAL_FORBIDDEN,
        decision.message or _MESSAGES[SELF_PROMOTION_FORBIDDEN],
        403,
    )
