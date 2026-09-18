from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses.models import Business
from app.modules.finance.errors import fin_error
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.promotion.ownership import assert_not_own_offer_for_partner_flow, user_owned_business_ids


async def assert_not_self_deal(
    db: AsyncSession,
    *,
    offer: Offer,
    partner_id: int,
    user_id: str | int | None = None,
) -> None:
    if user_id is not None:
        owned = await user_owned_business_ids(db, user_id)
        assert_not_own_offer_for_partner_flow(offer, owned)

    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.id == partner_id))
    if not partner:
        return
    business = await db.scalar(select(Business).where(Business.id == offer.business_id))
    if not business:
        return
    if (
        business.legal_entity_id
        and partner.legal_entity_id
        and business.legal_entity_id == partner.legal_entity_id
    ):
        raise fin_error(
            "FIN_SELF_DEAL_FORBIDDEN",
            "Partner promotion of an offer owned by the same legal entity is forbidden",
            403,
        )
