from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus, OfferStatus, PromotionOwner
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.ids import parse_id
from app.modules.businesses.models import BusinessMembership
from app.modules.campaigns.models import Campaign
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer

OWN_OFFER_MARKETPLACE_STATUSES = frozenset({OfferStatus.ACTIVE.value, OfferStatus.PAUSED.value})


async def user_owned_business_ids(db: AsyncSession, user_id: str | int) -> set[int]:
    rows = (
        await db.execute(
            select(BusinessMembership.business_id).where(
                BusinessMembership.user_id == parse_id(user_id),
                BusinessMembership.status == "active",
            )
        )
    ).scalars().all()
    return set(rows)


def is_own_offer(offer: Offer, owned_business_ids: set[int]) -> bool:
    return offer.business_id in owned_business_ids


def assert_not_own_offer_for_partner_flow(offer: Offer, owned_business_ids: set[int]) -> None:
    if is_own_offer(offer, owned_business_ids):
        raise ForbiddenError(
            "Собственный оффер продвигается через бизнес-пространство, без партнёрского доступа."
        )


def owner_type(*, partner_id: int | None, business_id: int | None) -> str:
    if business_id and not partner_id:
        return PromotionOwner.BUSINESS.value
    if partner_id and not business_id:
        return PromotionOwner.PARTNER.value
    raise AppError("PROMOTION_OWNER_INVALID", "Promotion must belong to either business or partner", 400)


def assert_exclusive_owner(*, partner_id: int | None, business_id: int | None) -> str:
    return owner_type(partner_id=partner_id, business_id=business_id)


def assert_offer_allows_new_promotion(offer: Offer) -> None:
    if offer.status != OfferStatus.ACTIVE.value:
        raise AppError(
            "OFFER_UNAVAILABLE",
            "Оффер больше недоступен для продвижения.",
            403,
        )


def campaign_owner_matches(
    campaign: Campaign,
    *,
    partner_id: int | None,
    business_id: int | None,
) -> bool:
    return campaign.partner_id == partner_id and campaign.business_id == business_id


async def require_offer_for_business(db: AsyncSession, offer_id: int, business_id: int) -> Offer:
    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id, Offer.business_id == business_id))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    return offer


async def resolve_campaign_for_owner(
    db: AsyncSession,
    *,
    campaign_id: int | None,
    offer_id: int,
    partner_id: int | None,
    business_id: int | None,
    allow_archived: bool = False,
) -> int | None:
    if campaign_id is None:
        return None
    campaign = (
        await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.offer_id == offer_id))
    ).scalar_one_or_none()
    if not campaign or not campaign_owner_matches(campaign, partner_id=partner_id, business_id=business_id):
        raise ForbiddenError("Campaign does not belong to this offer")
    if not allow_archived and campaign.status != CampaignStatus.ACTIVE.value:
        raise ForbiddenError("Archived campaign cannot be used for new links")
    return campaign.id


def default_link_name(destination_url: str, fallback: str = "Собственная ссылка") -> str:
    host = (urlparse(destination_url).hostname or "").removeprefix("www.")
    return host or fallback


def serialize_campaign(
    campaign: Campaign,
    *,
    offer_name: str | None = None,
    partner_name: str | None = None,
    links_count: int = 0,
    conversions_count: int = 0,
    clicks: int = 0,
    cr: float = 0.0,
) -> dict:
    payload = {
        "id": campaign.id,
        "offer_id": campaign.offer_id,
        "partner_id": campaign.partner_id,
        "business_id": campaign.business_id,
        "owner_type": campaign.owner_type,
        "name": campaign.name,
        "description": campaign.description,
        "type": campaign.campaign_type,
        "status": campaign.status,
        "links_count": links_count,
        "clicks": clicks,
        "conversions_count": conversions_count,
        "cr": cr,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }
    if offer_name is not None:
        payload["offer_name"] = offer_name
    if partner_name is not None:
        payload["partner_name"] = partner_name
    return payload


def serialize_link(
    link: TrackingLink,
    *,
    offer_name: str | None = None,
    campaign_name: str | None = None,
    partner_name: str | None = None,
    offer_image_url: str | None = None,
    offer_allowed_traffic: list[str] | None = None,
    offer_forbidden_traffic: list[str] | None = None,
    stats: dict | None = None,
) -> dict:
    payload = {
        "id": link.id,
        "offer_id": link.offer_id,
        "partner_id": link.partner_id,
        "business_id": link.business_id,
        "owner_type": link.owner_type,
        "campaign_id": link.campaign_id,
        "campaign_name": campaign_name,
        "partner_name": partner_name,
        "short_code": link.short_code,
        "url": f"https://go.refiq.ru/{link.short_code}",
        "destination_url": link.destination_url,
        "name": link.name,
        "traffic_source": link.traffic_source,
        "notes": link.notes,
        "status": link.status,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "updated_at": link.updated_at.isoformat() if link.updated_at else None,
    }
    if offer_name is not None:
        payload["offer_name"] = offer_name
    if offer_image_url is not None:
        payload["offer_image_url"] = offer_image_url
    if offer_allowed_traffic is not None:
        payload["offer_allowed_traffic"] = offer_allowed_traffic
    if offer_forbidden_traffic is not None:
        payload["offer_forbidden_traffic"] = offer_forbidden_traffic
    if stats is not None:
        payload["stats"] = stats
    return payload
