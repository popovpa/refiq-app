from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus, CampaignType
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_business_role, require_partner_role
from app.modules.campaigns.models import Campaign
from app.modules.conversions.models import Conversion
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile

router = APIRouter()
business_router = APIRouter()


class CreateCampaignRequest(BaseModel):
    offer_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class UpdateCampaignRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: CampaignStatus | None = None


def _serialize_campaign(
    campaign: Campaign,
    *,
    offer_name: str | None = None,
    partner_name: str | None = None,
    links_count: int = 0,
    conversions_count: int = 0,
) -> dict:
    payload = {
        "id": campaign.id,
        "offer_id": campaign.offer_id,
        "partner_id": campaign.partner_id,
        "name": campaign.name,
        "description": campaign.description,
        "type": campaign.campaign_type,
        "status": campaign.status,
        "links_count": links_count,
        "conversions_count": conversions_count,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }
    if offer_name is not None:
        payload["offer_name"] = offer_name
    if partner_name is not None:
        payload["partner_name"] = partner_name
    return payload


async def _get_partner_profile(user_id: str, db: AsyncSession) -> PartnerProfile:
    result = await db.execute(
        select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


async def _require_offer_access(offer_id: int, partner_id: int, db: AsyncSession) -> None:
    access = await db.scalar(
        select(OfferPartnerAccess.id).where(
            OfferPartnerAccess.offer_id == offer_id,
            OfferPartnerAccess.partner_id == partner_id,
            OfferPartnerAccess.status == "approved",
        )
    )
    if not access:
        raise ForbiddenError("No access to this offer")


async def _campaign_stats(db: AsyncSession, campaign_ids: list[int]) -> dict[int, tuple[int, int]]:
    if not campaign_ids:
        return {}
    links_rows = await db.execute(
        select(TrackingLink.campaign_id, func.count(TrackingLink.id))
        .where(TrackingLink.campaign_id.in_(campaign_ids))
        .group_by(TrackingLink.campaign_id)
    )
    conv_rows = await db.execute(
        select(TrackingLink.campaign_id, func.count(Conversion.id))
        .join(Conversion, Conversion.tracking_link_id == TrackingLink.id)
        .where(TrackingLink.campaign_id.in_(campaign_ids))
        .group_by(TrackingLink.campaign_id)
    )
    stats = {campaign_id: [0, 0] for campaign_id in campaign_ids}
    for campaign_id, count in links_rows.all():
        stats[campaign_id][0] = count
    for campaign_id, count in conv_rows.all():
        stats[campaign_id][1] = count
    return {key: (value[0], value[1]) for key, value in stats.items()}


@router.get("")
async def list_partner_campaigns(
    offer_id: int | None = Query(default=None),
    status: CampaignStatus | None = Query(default=None),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    query = (
        select(Campaign, Offer.name.label("offer_name"))
        .join(Offer, Campaign.offer_id == Offer.id)
        .where(Campaign.partner_id == profile.id)
    )
    if offer_id is not None:
        query = query.where(Campaign.offer_id == offer_id)
    if status is not None:
        query = query.where(Campaign.status == status.value)
    query = query.order_by(Campaign.created_at.desc())
    rows = (await db.execute(query)).all()
    stats = await _campaign_stats(db, [row.Campaign.id for row in rows])
    return {
        "items": [
            _serialize_campaign(
                row.Campaign,
                offer_name=row.offer_name,
                links_count=stats.get(row.Campaign.id, (0, 0))[0],
                conversions_count=stats.get(row.Campaign.id, (0, 0))[1],
            )
            for row in rows
        ]
    }


@router.post("")
async def create_partner_campaign(
    data: CreateCampaignRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    await _require_offer_access(data.offer_id, profile.id, db)
    campaign = Campaign(
        offer_id=data.offer_id,
        partner_id=profile.id,
        name=data.name.strip(),
        description=(data.description or "").strip() or None,
        campaign_type=CampaignType.GENERAL.value,
        status=CampaignStatus.ACTIVE.value,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return _serialize_campaign(campaign)


@router.patch("/{campaign_id}")
async def update_partner_campaign(
    campaign_id: int,
    data: UpdateCampaignRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.partner_id == profile.id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise NotFoundError("Campaign")

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        campaign.name = update_data["name"].strip()
    if "description" in update_data:
        description = update_data["description"]
        campaign.description = description.strip() if isinstance(description, str) and description.strip() else None
    if "status" in update_data and update_data["status"] is not None:
        campaign.status = update_data["status"].value
    return _serialize_campaign(campaign)


@router.get("/{campaign_id}/links")
async def list_campaign_links(
    campaign_id: int,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    campaign = (
        await db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.partner_id == profile.id)
        )
    ).scalar_one_or_none()
    if not campaign:
        raise NotFoundError("Campaign")

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
            select(Campaign, Offer.name.label("offer_name"), PartnerProfile.display_name.label("partner_name"))
            .join(Offer, Campaign.offer_id == Offer.id)
            .join(PartnerProfile, Campaign.partner_id == PartnerProfile.id)
            .where(Offer.business_id == business_id)
            .order_by(Campaign.created_at.desc())
        )
    ).all()
    stats = await _campaign_stats(db, [row.Campaign.id for row in rows])
    return {
        "items": [
            _serialize_campaign(
                row.Campaign,
                offer_name=row.offer_name,
                partner_name=row.partner_name,
                links_count=stats.get(row.Campaign.id, (0, 0))[0],
                conversions_count=stats.get(row.Campaign.id, (0, 0))[1],
            )
            for row in rows
        ]
    }
