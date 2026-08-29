from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.ids import parse_id
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile


async def get_business_offer(db: AsyncSession, offer_id: str | int, business_id: int) -> Offer:
    offer = (
        await db.execute(
            select(Offer).where(Offer.id == parse_id(offer_id), Offer.business_id == business_id)
        )
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    return offer


async def get_partner_profile(db: AsyncSession, user_id: str | int) -> PartnerProfile:
    profile = (
        await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id)))
    ).scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


async def get_partner_offer(
    db: AsyncSession,
    offer_id: str | int,
    partner_id: int,
    *,
    require_approved: bool = False,
) -> tuple[Offer, OfferPartnerAccess | None]:
    offer = (
        await db.execute(select(Offer).where(Offer.id == parse_id(offer_id)))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == partner_id,
            )
        )
    ).scalar_one_or_none()
    visible = offer.status == "active" and offer.visibility == "public"
    if not visible and (not access or access.status not in {"approved", "pending"}):
        raise NotFoundError("Offer")
    if require_approved and (not access or access.status != "approved"):
        raise ForbiddenError("Offer is not available for promotion")
    return offer, access
