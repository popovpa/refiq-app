from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_business_role, require_partner_role
from app.modules.campaigns.models import Campaign
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile
from app.modules.partners.privacy import partner_public_display_name_from
from app.modules.users.models import User
from app.modules.promotion.campaigns import (
    campaign_payload,
    campaign_stats,
    create_campaign,
    get_owned_campaign,
    list_owner_campaigns,
    update_campaign,
)
from app.modules.promotion.ownership import require_offer_for_business, serialize_campaign, serialize_link

router = APIRouter()
business_router = APIRouter()


class CreateCampaignRequest(BaseModel):
    offer_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class CreateOfferCampaignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class UpdateCampaignRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: CampaignStatus | None = None


async def _get_partner_profile(user_id: str, db: AsyncSession) -> PartnerProfile:
    result = await db.execute(
        select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


async def _require_offer_access(offer_id: int, partner_id: int, db: AsyncSession) -> Offer:
    offer = (await db.execute(select(Offer).where(Offer.id == offer_id))).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    access = await db.scalar(
        select(OfferPartnerAccess.id).where(
            OfferPartnerAccess.offer_id == offer_id,
            OfferPartnerAccess.partner_id == partner_id,
            OfferPartnerAccess.status == "approved",
        )
    )
    if not access:
        raise ForbiddenError("No access to this offer")
    return offer


@router.get("")
async def list_partner_campaigns(
    offer_id: int | None = Query(default=None),
    status: CampaignStatus | None = Query(default=None),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    rows = await list_owner_campaigns(db, offer_id=offer_id, partner_id=profile.id, status=status)
    stats = await campaign_stats(db, [campaign.id for campaign, _name in rows])
    return {
        "items": [
            campaign_payload(campaign, stats, offer_name=offer_name)
            for campaign, offer_name in rows
        ]
    }


@router.post("")
async def create_partner_campaign(
    data: CreateCampaignRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    offer = await _require_offer_access(data.offer_id, profile.id, db)
    from app.modules.finance.self_deal import assert_not_self_deal
    from app.modules.finance.suspension import assert_partner_promotion_allowed

    await assert_not_self_deal(db, offer=offer, partner_id=profile.id, user_id=session_data["user_id"])
    await assert_partner_promotion_allowed(db, offer.business_id)
    campaign = await create_campaign(
        db,
        offer=offer,
        name=data.name,
        description=data.description,
        partner_id=profile.id,
        require_active_offer=False,
    )
    return serialize_campaign(campaign)


@router.patch("/{campaign_id}")
async def update_partner_campaign(
    campaign_id: int,
    data: UpdateCampaignRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    campaign = await get_owned_campaign(db, campaign_id=campaign_id, partner_id=profile.id)
    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        campaign.name = update_data["name"].strip()
    if "description" in update_data:
        description = update_data["description"]
        campaign.description = description.strip() if isinstance(description, str) and description.strip() else None
    if "status" in update_data and update_data["status"] is not None:
        campaign.status = update_data["status"].value
    return serialize_campaign(campaign)


@router.get("/{campaign_id}/links")
async def list_campaign_links(
    campaign_id: int,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    campaign = await get_owned_campaign(db, campaign_id=campaign_id, partner_id=profile.id)
    result = await db.execute(
        select(TrackingLink)
        .where(TrackingLink.campaign_id == campaign.id, TrackingLink.partner_id == profile.id)
        .order_by(TrackingLink.created_at.desc())
    )
    items = [
        {
            "id": link.id,
            "short_code": link.short_code,
            "url": f"https://go.refiq.ru/{link.short_code}",
            "destination_url": link.destination_url,
            "status": link.status,
        }
        for link in result.scalars().all()
    ]
    return {"items": items}


@business_router.get("/campaigns")
async def list_business_campaigns(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    rows = (
        await db.execute(
            select(Campaign, Offer.name.label("offer_name"), PartnerProfile, User)
            .join(Offer, Campaign.offer_id == Offer.id)
            .join(PartnerProfile, Campaign.partner_id == PartnerProfile.id)
            .join(User, PartnerProfile.user_id == User.id)
            .where(Offer.business_id == business_id, Campaign.partner_id.is_not(None))
            .order_by(Campaign.created_at.desc())
        )
    ).all()
    stats = await campaign_stats(db, [row.Campaign.id for row in rows])
    return {
        "items": [
            campaign_payload(
                row.Campaign,
                stats,
                offer_name=row.offer_name,
                partner_name=partner_public_display_name_from(row.PartnerProfile, row.User),
            )
            for row in rows
        ]
    }


@business_router.get("/offers/{offer_id}/campaigns")
async def list_business_offer_campaigns(
    offer_id: str,
    status: CampaignStatus | None = Query(default=None),
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    rows = await list_owner_campaigns(
        db, offer_id=offer.id, business_id=business_id, status=status
    )
    stats = await campaign_stats(db, [campaign.id for campaign, _name in rows])
    return {
        "items": [campaign_payload(campaign, stats, offer_name=offer_name) for campaign, offer_name in rows]
    }


@business_router.post("/offers/{offer_id}/campaigns")
async def create_business_offer_campaign(
    offer_id: str,
    data: CreateOfferCampaignRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    campaign = await create_campaign(
        db,
        offer=offer,
        name=data.name,
        description=data.description,
        business_id=business_id,
    )
    return serialize_campaign(campaign)


@business_router.patch("/offers/{offer_id}/campaigns/{campaign_id}")
async def update_business_offer_campaign(
    offer_id: str,
    campaign_id: int,
    data: UpdateCampaignRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    campaign = await get_owned_campaign(
        db, campaign_id=campaign_id, business_id=business_id, offer_id=offer.id
    )
    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        campaign.name = update_data["name"].strip()
    if "description" in update_data:
        description = update_data["description"]
        campaign.description = description.strip() if isinstance(description, str) and description.strip() else None
    if "status" in update_data and update_data["status"] is not None:
        campaign.status = update_data["status"].value
    return serialize_campaign(campaign)


@business_router.get("/offers/{offer_id}/campaigns/{campaign_id}/links")
async def list_business_offer_campaign_links(
    offer_id: str,
    campaign_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    campaign = await get_owned_campaign(
        db, campaign_id=campaign_id, business_id=business_id, offer_id=offer.id
    )
    result = await db.execute(
        select(TrackingLink)
        .where(TrackingLink.campaign_id == campaign.id, TrackingLink.business_id == business_id)
        .order_by(TrackingLink.created_at.desc())
    )
    return {"items": [serialize_link(link) for link in result.scalars().all()]}
