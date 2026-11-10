from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.core.ids import parse_id
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.businesses.models import BusinessMembership
from app.modules.campaigns.models import Campaign
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile
from app.modules.sites.models import Site

Role = Literal["business", "partner"]


@dataclass
class AnalyticsScope:
    role: Role
    user_id: int
    business_id: int | None
    partner_id: int | None


async def resolve_scope(db: AsyncSession, session_data: dict) -> AnalyticsScope:
    role = session_data.get("active_role")
    try:
        user_id = parse_id(session_data.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise ForbiddenError("Access denied") from exc
    if role == "business":
        try:
            business_id = parse_id(session_data.get("active_business_id"))
        except (TypeError, ValueError) as exc:
            raise ForbiddenError("Business role required") from exc
        membership = await db.scalar(
            select(BusinessMembership.id).where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.business_id == business_id,
                BusinessMembership.status == "active",
            )
        )
        if membership is None:
            raise ForbiddenError("Business role required")
        return AnalyticsScope("business", user_id, business_id, None)
    if role == "partner":
        partner_id = await db.scalar(
            select(PartnerProfile.id).where(PartnerProfile.user_id == user_id)
        )
        if partner_id is None:
            raise ForbiddenError("Partner profile required")
        return AnalyticsScope("partner", user_id, None, int(partner_id))
    raise ForbiddenError("Access denied")


async def authorize_filters(db: AsyncSession, scope: AnalyticsScope, filt: AnalyticsFilters) -> None:
    if scope.role == "partner" and filt.site_id is not None:
        raise ForbiddenError("Access denied")
    if scope.role == "partner" and filt.partner_id is not None and filt.partner_id != scope.partner_id:
        raise ForbiddenError("Access denied")
    if filt.offer_id is not None:
        await _require_offer(db, scope, filt.offer_id)
    if filt.campaign_id is not None:
        await _require_campaign(db, scope, filt.campaign_id)
    if filt.link_id is not None:
        await _require_link(db, scope, filt.link_id)
    if filt.site_id is not None:
        await _require_site(db, scope, filt.site_id)
    if scope.role == "business" and filt.partner_id is not None:
        await _require_partner(db, scope, filt.partner_id)


async def _require_offer(db: AsyncSession, scope: AnalyticsScope, offer_id: int) -> None:
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise ForbiddenError("Access denied")
    if scope.role == "business":
        if offer.business_id != scope.business_id:
            raise ForbiddenError("Access denied")
        return
    link = await db.scalar(
        select(TrackingLink.id).where(
            TrackingLink.offer_id == offer_id,
            TrackingLink.partner_id == scope.partner_id,
        )
    )
    access = await db.scalar(
        select(OfferPartnerAccess.id).where(
            OfferPartnerAccess.offer_id == offer_id,
            OfferPartnerAccess.partner_id == scope.partner_id,
        )
    )
    if link is None and access is None:
        raise ForbiddenError("Access denied")


async def _require_campaign(db: AsyncSession, scope: AnalyticsScope, campaign_id: int) -> None:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise ForbiddenError("Access denied")
    offer = await db.get(Offer, campaign.offer_id)
    if offer is None:
        raise ForbiddenError("Access denied")
    if scope.role == "business":
        if offer.business_id != scope.business_id:
            raise ForbiddenError("Access denied")
        return
    if campaign.partner_id != scope.partner_id:
        raise ForbiddenError("Access denied")


async def _require_link(db: AsyncSession, scope: AnalyticsScope, link_id: int) -> None:
    link = await db.get(TrackingLink, link_id)
    if link is None:
        raise ForbiddenError("Access denied")
    if scope.role == "partner":
        if link.partner_id != scope.partner_id:
            raise ForbiddenError("Access denied")
        return
    offer = await db.get(Offer, link.offer_id)
    if offer is None or offer.business_id != scope.business_id:
        raise ForbiddenError("Access denied")


async def _require_site(db: AsyncSession, scope: AnalyticsScope, site_id: int) -> None:
    site = await db.get(Site, site_id)
    if site is None or site.business_id != scope.business_id:
        raise ForbiddenError("Access denied")


async def _require_partner(db: AsyncSession, scope: AnalyticsScope, partner_id: int) -> None:
    from app.modules.conversions.models import Conversion

    link = await db.scalar(
        select(TrackingLink.id)
        .join(Offer, Offer.id == TrackingLink.offer_id)
        .where(Offer.business_id == scope.business_id, TrackingLink.partner_id == partner_id)
    )
    if link is not None:
        return
    access = await db.scalar(
        select(OfferPartnerAccess.id)
        .join(Offer, Offer.id == OfferPartnerAccess.offer_id)
        .where(Offer.business_id == scope.business_id, OfferPartnerAccess.partner_id == partner_id)
    )
    if access is not None:
        return
    owned = await db.scalar(
        select(Conversion.id).where(
            Conversion.business_id == scope.business_id,
            Conversion.partner_id == partner_id,
        )
    )
    if owned is None:
        raise ForbiddenError("Access denied")
