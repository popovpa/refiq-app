from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus, CampaignType
from app.core.exceptions import NotFoundError
from app.modules.campaigns.models import Campaign
from app.modules.conversions.models import Conversion
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer
from app.modules.promotion.ownership import (
    assert_exclusive_owner,
    assert_offer_allows_new_promotion,
    serialize_campaign,
)


async def campaign_stats(db: AsyncSession, campaign_ids: list[int]) -> dict[int, dict[str, int | float]]:
    if not campaign_ids:
        return {}
    from app.modules.links.models import Click
    from app.modules.offers.service import cr

    links_rows = await db.execute(
        select(TrackingLink.campaign_id, func.count(TrackingLink.id))
        .where(TrackingLink.campaign_id.in_(campaign_ids))
        .group_by(TrackingLink.campaign_id)
    )
    click_rows = await db.execute(
        select(TrackingLink.campaign_id, func.count(Click.id))
        .join(Click, Click.tracking_link_id == TrackingLink.id)
        .where(TrackingLink.campaign_id.in_(campaign_ids))
        .group_by(TrackingLink.campaign_id)
    )
    conv_rows = await db.execute(
        select(TrackingLink.campaign_id, func.count(Conversion.id))
        .join(Conversion, Conversion.tracking_link_id == TrackingLink.id)
        .where(TrackingLink.campaign_id.in_(campaign_ids))
        .group_by(TrackingLink.campaign_id)
    )
    stats: dict[int, dict[str, int | float]] = {
        campaign_id: {"links_count": 0, "clicks": 0, "conversions": 0, "cr": 0.0}
        for campaign_id in campaign_ids
    }
    for campaign_id, count in links_rows.all():
        stats[campaign_id]["links_count"] = int(count)
    for campaign_id, count in click_rows.all():
        stats[campaign_id]["clicks"] = int(count)
    for campaign_id, count in conv_rows.all():
        stats[campaign_id]["conversions"] = int(count)
    for item in stats.values():
        item["cr"] = cr(int(item["clicks"]), int(item["conversions"]))
    return stats


async def create_campaign(
    db: AsyncSession,
    *,
    offer: Offer,
    name: str,
    description: str | None = None,
    partner_id: int | None = None,
    business_id: int | None = None,
    require_active_offer: bool = True,
) -> Campaign:
    assert_exclusive_owner(partner_id=partner_id, business_id=business_id)
    if require_active_offer:
        assert_offer_allows_new_promotion(offer)
    campaign = Campaign(
        offer_id=offer.id,
        partner_id=partner_id,
        business_id=business_id,
        name=name.strip(),
        description=(description or "").strip() or None,
        campaign_type=CampaignType.GENERAL.value,
        status=CampaignStatus.ACTIVE.value,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    campaign: Campaign,
    *,
    name: str | None = None,
    description: str | None = None,
    status: CampaignStatus | None = None,
) -> Campaign:
    if name is not None:
        campaign.name = name.strip()
    if description is not None:
        campaign.description = description.strip() if description.strip() else None
    if status is not None:
        campaign.status = status.value
    return campaign


async def get_owned_campaign(
    db: AsyncSession,
    *,
    campaign_id: int,
    partner_id: int | None = None,
    business_id: int | None = None,
    offer_id: int | None = None,
) -> Campaign:
    query = select(Campaign).where(Campaign.id == campaign_id)
    if partner_id is not None:
        query = query.where(Campaign.partner_id == partner_id)
    if business_id is not None:
        query = query.where(Campaign.business_id == business_id)
    if offer_id is not None:
        query = query.where(Campaign.offer_id == offer_id)
    campaign = (await db.execute(query)).scalar_one_or_none()
    if not campaign:
        raise NotFoundError("Campaign")
    return campaign


async def list_owner_campaigns(
    db: AsyncSession,
    *,
    offer_id: int | None = None,
    partner_id: int | None = None,
    business_id: int | None = None,
    status: CampaignStatus | None = None,
) -> list[tuple[Campaign, str]]:
    query = select(Campaign, Offer.name.label("offer_name")).join(Offer, Campaign.offer_id == Offer.id)
    if partner_id is not None:
        query = query.where(Campaign.partner_id == partner_id)
    if business_id is not None:
        query = query.where(Campaign.business_id == business_id)
    if offer_id is not None:
        query = query.where(Campaign.offer_id == offer_id)
    if status is not None:
        query = query.where(Campaign.status == status.value)
    query = query.order_by(Campaign.created_at.desc())
    rows = (await db.execute(query)).all()
    return [(row.Campaign, row.offer_name) for row in rows]


def campaign_payload(campaign: Campaign, stats: dict[int, dict[str, int | float]], **extra) -> dict:
    item = stats.get(campaign.id) or {}
    return serialize_campaign(
        campaign,
        links_count=int(item.get("links_count") or 0),
        conversions_count=int(item.get("conversions") or 0),
        clicks=int(item.get("clicks") or 0),
        cr=float(item.get("cr") or 0),
        **extra,
    )
