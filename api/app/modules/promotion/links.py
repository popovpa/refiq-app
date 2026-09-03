from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LinkStatus as TrackingLinkStatus
from app.modules.links.models import TrackingLink
from app.modules.links.short_code import generate_short_code
from app.modules.links.destination import assert_destination_allowed
from app.modules.offers.models import Offer
from app.modules.promotion.ownership import (
    assert_exclusive_owner,
    assert_offer_allows_new_promotion,
    default_link_name,
    resolve_campaign_for_owner,
)
from app.modules.qr.service import QrCodeService


async def allocate_unique_short_code(db: AsyncSession) -> str:
    for _ in range(16):
        candidate = generate_short_code()
        exists = await db.scalar(select(TrackingLink.id).where(TrackingLink.short_code == candidate))
        if not exists:
            return candidate
    raise RuntimeError("Failed to generate a unique short code")


async def create_tracking_link(
    db: AsyncSession,
    *,
    offer: Offer,
    destination_url: str,
    name: str | None,
    traffic_source: str | None = None,
    notes: str | None = None,
    campaign_id: int | None = None,
    partner_id: int | None = None,
    business_id: int | None = None,
) -> TrackingLink:
    assert_exclusive_owner(partner_id=partner_id, business_id=business_id)
    resolved_campaign_id = await resolve_campaign_for_owner(
        db,
        campaign_id=campaign_id,
        offer_id=offer.id,
        partner_id=partner_id,
        business_id=business_id,
    )
    if business_id is not None:
        assert_offer_allows_new_promotion(offer)
    destination = await assert_destination_allowed(db, business_id=offer.business_id, url=destination_url)
    link_name = (name or "").strip() or default_link_name(destination)
    link = TrackingLink(
        offer_id=offer.id,
        partner_id=partner_id,
        business_id=business_id,
        campaign_id=resolved_campaign_id,
        short_code=await allocate_unique_short_code(db),
        destination_url=destination,
        name=link_name,
        traffic_source=(traffic_source or "").strip() or None,
        notes=(notes or "").strip() or None,
        status=TrackingLinkStatus.ACTIVE.value,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    await QrCodeService().create_quietly(link.short_code)
    return link
