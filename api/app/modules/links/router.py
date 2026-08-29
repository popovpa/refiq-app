from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus, CampaignType
from app.core.database import get_db
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.ids import parse_id, parse_optional_id
from app.core.permissions import require_partner_role
from app.modules.campaigns.models import Campaign
from app.modules.links.destination import assert_destination_allowed
from app.modules.links.models import TrackingLink, TrackingLinkStatus
from app.modules.links.short_code import generate_short_code
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.offers.service import product_url_for_offer
from app.modules.links.service import (
    assert_can_activate_link,
    batch_link_stats,
    build_link_filters,
    link_filter_options,
    links_summary,
)
from app.modules.partners.models import PartnerProfile
from app.modules.qr.service import QrCodeService, png_response

router = APIRouter()


class CreateLinkRequest(BaseModel):
    offer_id: int
    name: str = Field(min_length=1, max_length=255)
    traffic_source: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    destination_url: HttpUrl | None = None
    campaign_id: int | None = None


class UpdateLinkRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    traffic_source: str | None = Field(default=None, min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    destination_url: HttpUrl | None = None
    campaign_id: int | None = None
    status: TrackingLinkStatus | None = None


def _serialize_link(
    link: TrackingLink,
    offer_name: str | None = None,
    campaign_name: str | None = None,
    offer_image_url: str | None = None,
    offer_allowed_traffic: list[str] | None = None,
    offer_forbidden_traffic: list[str] | None = None,
    stats: dict | None = None,
) -> dict:
    payload = {
        "id": link.id,
        "offer_id": link.offer_id,
        "partner_id": link.partner_id,
        "campaign_id": link.campaign_id,
        "campaign_name": campaign_name,
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


def _assert_traffic_source_allowed(offer: Offer, traffic_source: str) -> None:
    forbidden = set(offer.forbidden_traffic or [])
    allowed = offer.allowed_traffic or []
    if traffic_source in forbidden or (allowed and traffic_source not in allowed):
        raise AppError(
            "TRAFFIC_SOURCE_FORBIDDEN",
            "Этот источник трафика запрещён для оффера.",
            400,
        )


async def _get_partner_profile(user_id: str, db: AsyncSession) -> PartnerProfile:
    result = await db.execute(
        select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


async def _unique_short_code(db: AsyncSession) -> str:
    for _ in range(16):
        candidate = generate_short_code()
        exists = await db.scalar(
            select(TrackingLink.id).where(TrackingLink.short_code == candidate)
        )
        if not exists:
            return candidate
    raise RuntimeError("Failed to generate a unique short code")


async def _resolve_campaign(
    db: AsyncSession,
    *,
    campaign_id: int | None,
    offer_id: int,
    partner_id: int,
    allow_archived: bool = False,
) -> int | None:
    if campaign_id is None:
        return None
    campaign = (
        await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.partner_id == partner_id,
                Campaign.offer_id == offer_id,
            )
        )
    ).scalar_one_or_none()
    if not campaign:
        raise ForbiddenError("Campaign does not belong to this offer")
    if not allow_archived and campaign.status != CampaignStatus.ACTIVE.value:
        raise ForbiddenError("Archived campaign cannot be used for new links")
    return campaign.id


async def _create_general_campaign(
    db: AsyncSession,
    *,
    offer_id: int,
    partner_id: int,
    name: str,
) -> int:
    campaign = Campaign(
        offer_id=offer_id,
        partner_id=partner_id,
        name=name,
        campaign_type=CampaignType.GENERAL.value,
        status=CampaignStatus.ACTIVE.value,
    )
    db.add(campaign)
    await db.flush()
    return campaign.id


@router.get("")
async def list_links(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    days: int = Query(default=7, ge=1, le=90),
    q: str | None = None,
    offer_id: int | None = None,
    traffic_source: str | None = None,
    status: str | None = None,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    filters = build_link_filters(
        partner_id=profile.id,
        q=q,
        offer_id=offer_id,
        traffic_source=traffic_source,
        status=status,
    )

    total = await db.scalar(
        select(func.count(TrackingLink.id))
        .select_from(TrackingLink)
        .join(Offer, TrackingLink.offer_id == Offer.id)
        .where(*filters)
    )
    result = await db.execute(
        select(
            TrackingLink,
            Offer.name.label("offer_name"),
            Offer.image_url.label("offer_image_url"),
            Offer.allowed_traffic.label("offer_allowed_traffic"),
            Offer.forbidden_traffic.label("offer_forbidden_traffic"),
            Campaign.name.label("campaign_name"),
        )
        .join(Offer, TrackingLink.offer_id == Offer.id)
        .outerjoin(Campaign, TrackingLink.campaign_id == Campaign.id)
        .where(*filters)
        .order_by(TrackingLink.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()
    link_ids = [row.TrackingLink.id for row in rows]
    stats_map = await batch_link_stats(db, link_ids, profile.id, days)
    summary = await links_summary(db, partner_id=profile.id, days=days, filters=filters)
    filter_options = await link_filter_options(db, profile.id)

    items = [
        _serialize_link(
            row.TrackingLink,
            row.offer_name,
            row.campaign_name,
            row.offer_image_url,
            row.offer_allowed_traffic or [],
            row.offer_forbidden_traffic or [],
            stats_map.get(row.TrackingLink.id),
        )
        for row in rows
    ]

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "per_page": per_page,
        "summary": summary,
        "days": days,
        "filter_options": filter_options,
    }


@router.post("")
async def create_link(
    data: CreateLinkRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    link_name = data.name.strip()
    traffic_source = data.traffic_source.strip()
    notes = (data.notes or "").strip() or None

    offer = (
        await db.execute(select(Offer).where(Offer.id == data.offer_id))
    ).scalar_one_or_none()
    if not offer or offer.status != "active":
        raise AppError(
            "OFFER_UNAVAILABLE",
            "Оффер больше недоступен для продвижения.",
            403,
        )

    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == profile.id,
                OfferPartnerAccess.status == "approved",
            )
        )
    ).scalar_one_or_none()
    if not access:
        raise AppError(
            "OFFER_APPROVAL_REQUIRED",
            "Для этого оффера требуется одобрение.",
            403,
        )

    _assert_traffic_source_allowed(offer, traffic_source)

    destination = str(data.destination_url) if data.destination_url else await product_url_for_offer(db, offer)
    if not destination:
        raise AppError("OFFER_LANDING_MISSING", "Для оффера не задана страница продукта", 400)
    destination = await assert_destination_allowed(db, business_id=offer.business_id, url=destination)

    if data.campaign_id is not None:
        campaign_id = await _resolve_campaign(
            db,
            campaign_id=data.campaign_id,
            offer_id=data.offer_id,
            partner_id=profile.id,
        )
    else:
        campaign_id = await _create_general_campaign(
            db,
            offer_id=data.offer_id,
            partner_id=profile.id,
            name=link_name,
        )

    short_code = await _unique_short_code(db)

    link = TrackingLink(
        offer_id=data.offer_id,
        partner_id=profile.id,
        campaign_id=campaign_id,
        short_code=short_code,
        destination_url=destination,
        name=link_name,
        traffic_source=traffic_source,
        notes=notes,
        status=TrackingLinkStatus.ACTIVE.value,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    await QrCodeService().create_quietly(link.short_code)

    return _serialize_link(link, offer_name=offer.name, offer_image_url=offer.image_url)


@router.patch("/{link_id}")
async def update_link(
    link_id: str,
    data: UpdateLinkRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)

    result = await db.execute(
        select(TrackingLink).where(
            TrackingLink.id == parse_id(link_id),
            TrackingLink.partner_id == profile.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("Link")

    offer = (
        await db.execute(select(Offer).where(Offer.id == link.offer_id))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()
    if "traffic_source" in update_data and update_data["traffic_source"] is not None:
        update_data["traffic_source"] = update_data["traffic_source"].strip()
        _assert_traffic_source_allowed(offer, update_data["traffic_source"])
    if "notes" in update_data:
        notes = update_data["notes"]
        update_data["notes"] = notes.strip() if isinstance(notes, str) and notes.strip() else None
    if "destination_url" in update_data:
        raise AppError(
            "DESTINATION_EDIT_FORBIDDEN",
            "Целевую страницу может изменить только бизнес.",
            403,
        )
    if "campaign_id" in update_data:
        update_data["campaign_id"] = await _resolve_campaign(
            db,
            campaign_id=parse_optional_id(update_data["campaign_id"]),
            offer_id=link.offer_id,
            partner_id=profile.id,
        )
    if "status" in update_data and update_data["status"] is not None:
        new_status = update_data["status"].value
        if new_status == TrackingLinkStatus.ACTIVE.value and link.status != TrackingLinkStatus.ACTIVE.value:
            await assert_can_activate_link(db, link=link, profile=profile, user_id=user_id)
        update_data["status"] = new_status
    for key, value in update_data.items():
        setattr(link, key, value)

    return _serialize_link(
        link,
        offer_name=offer.name,
        offer_image_url=offer.image_url,
        offer_allowed_traffic=offer.allowed_traffic or [],
        offer_forbidden_traffic=offer.forbidden_traffic or [],
    )


@router.patch("/{link_id}/disable")
async def disable_link(
    link_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)

    result = await db.execute(
        select(TrackingLink).where(
            TrackingLink.id == parse_id(link_id),
            TrackingLink.partner_id == profile.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("Link")
    if link.status != TrackingLinkStatus.DISABLED.value:
        link.status = TrackingLinkStatus.DISABLED.value
    return {"status": "ok"}


async def _get_owned_partner_link(
    db: AsyncSession,
    *,
    link_id: str,
    partner_id: int,
) -> TrackingLink:
    result = await db.execute(
        select(TrackingLink).where(
            TrackingLink.id == parse_id(link_id),
            TrackingLink.partner_id == partner_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("Link")
    return link


@router.get("/{link_id}/qr-code")
async def get_link_qr_code(
    link_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    link = await _get_owned_partner_link(db, link_id=link_id, partner_id=profile.id)
    data = await QrCodeService().get_or_create(link.short_code)
    return png_response(data)


@router.get("/{link_id}/qr-code/download")
async def download_link_qr_code(
    link_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    link = await _get_owned_partner_link(db, link_id=link_id, partner_id=profile.id)
    data = await QrCodeService().get_or_create(link.short_code)
    return png_response(data, as_attachment=True, short_code=link.short_code)
