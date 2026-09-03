from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LinkStatus as TrackingLinkStatus
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.campaigns.models import Campaign
from app.modules.links.destination import assert_destination_allowed
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer
from app.modules.offers.service import offer_link_stats
from app.modules.partners.models import PartnerProfile
from app.modules.promotion.links import create_tracking_link
from app.modules.promotion.ownership import assert_offer_allows_new_promotion, require_offer_for_business, serialize_link
from app.modules.system.audit import actor_display_name, write_audit_log
from app.modules.system.models import AuditLog
from app.modules.users.models import User
from app.modules.qr.service import QrCodeService, png_response
from app.modules.sites.service import SiteService

router = APIRouter()

DESTINATION_UPDATED_ACTION = "tracking_link.destination_updated"


class UpdateDestinationRequest(BaseModel):
    destination_url: str = Field(min_length=1, max_length=500)


class CreateBusinessLinkRequest(BaseModel):
    destination_url: HttpUrl
    campaign_id: int | None = None
    name: str | None = Field(default=None, max_length=255)


class UpdateBusinessLinkStatusRequest(BaseModel):
    status: TrackingLinkStatus


def _serialize_business_link(link: TrackingLink, partner_name: str | None = None) -> dict:
    return {
        "id": link.id,
        "offer_id": link.offer_id,
        "partner_id": link.partner_id,
        "partner_name": partner_name,
        "business_id": link.business_id,
        "owner_type": link.owner_type,
        "campaign_id": link.campaign_id,
        "name": link.name,
        "short_code": link.short_code,
        "url": f"https://go.refiq.ru/{link.short_code}",
        "destination_url": link.destination_url,
        "traffic_source": link.traffic_source,
        "status": link.status,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "updated_at": link.updated_at.isoformat() if link.updated_at else None,
    }


async def _with_site_match(db: AsyncSession, business_id: int, payload: dict) -> dict:
    match = await SiteService(db).match_destination(business_id, payload.get("destination_url"))
    payload.update(match)
    return payload


@router.get("/offers/{offer_id}/links")
async def list_business_own_links(
    offer_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    rows = (
        await db.execute(
            select(TrackingLink, Campaign.name.label("campaign_name"))
            .outerjoin(Campaign, TrackingLink.campaign_id == Campaign.id)
            .where(TrackingLink.offer_id == offer.id, TrackingLink.business_id == business_id)
            .order_by(TrackingLink.created_at.desc())
        )
    ).all()
    stats_by_link = await offer_link_stats(db, offer.id)
    items = []
    for link, campaign_name in rows:
        link_stats = stats_by_link.get(link.id, {"clicks": 0, "conversions": 0})
        payload = serialize_link(link, campaign_name=campaign_name, stats=link_stats)
        items.append(await _with_site_match(db, business_id, payload))
    return {"items": items}


@router.post("/offers/{offer_id}/links")
async def create_business_own_link(
    offer_id: str,
    data: CreateBusinessLinkRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await require_offer_for_business(db, parse_id(offer_id), business_id)
    link = await create_tracking_link(
        db,
        offer=offer,
        destination_url=str(data.destination_url),
        name=data.name,
        campaign_id=data.campaign_id,
        business_id=business_id,
    )
    campaign_name = None
    if link.campaign_id:
        campaign = (await db.execute(select(Campaign).where(Campaign.id == link.campaign_id))).scalar_one_or_none()
        campaign_name = campaign.name if campaign else None
    return serialize_link(link, campaign_name=campaign_name)


@router.patch("/offers/{offer_id}/links/{link_id}/status")
async def update_business_own_link_status(
    offer_id: str,
    link_id: str,
    data: UpdateBusinessLinkStatusRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=business_id,
    )
    if link.business_id != business_id:
        raise AppError("PROMOTION_OWNER_INVALID", "Можно изменять только собственные ссылки.", 403)
    new_status = data.status.value
    if new_status == TrackingLinkStatus.ACTIVE.value and link.status != TrackingLinkStatus.ACTIVE.value:
        assert_offer_allows_new_promotion(offer)
    link.status = new_status
    return serialize_link(link)


async def _get_owned_link(
    db: AsyncSession,
    *,
    offer_id: str,
    link_id: str,
    business_id: str | int,
) -> tuple[Offer, TrackingLink]:
    offer = (
        await db.execute(
            select(Offer).where(
                Offer.id == parse_id(offer_id),
                Offer.business_id == parse_id(business_id),
            )
        )
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    link = (
        await db.execute(
            select(TrackingLink).where(
                TrackingLink.id == parse_id(link_id),
                TrackingLink.offer_id == offer.id,
            )
        )
    ).scalar_one_or_none()
    if not link:
        raise NotFoundError("Link")
    return offer, link


@router.get("/offers/{offer_id}/links/{link_id}")
async def get_business_link(
    offer_id: str,
    link_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=parse_id(session_data["active_business_id"]),
    )
    profile = (
        await db.execute(select(PartnerProfile).where(PartnerProfile.id == link.partner_id))
    ).scalar_one_or_none()
    payload = _serialize_business_link(link, profile.display_name if profile else None)
    payload["offer_name"] = offer.name
    return await _with_site_match(db, parse_id(session_data["active_business_id"]), payload)


@router.patch("/offers/{offer_id}/links/{link_id}")
async def update_business_link_destination(
    offer_id: str,
    link_id: str,
    data: UpdateDestinationRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=business_id,
    )
    new_url = await assert_destination_allowed(db, business_id=business_id, url=data.destination_url)
    old_url = link.destination_url
    profile = (
        await db.execute(select(PartnerProfile).where(PartnerProfile.id == link.partner_id))
    ).scalar_one_or_none()
    if old_url != new_url:
        user = (
            await db.execute(select(User).where(User.id == parse_id(session_data["user_id"])))
        ).scalar_one_or_none()
        link.destination_url = new_url
        await write_audit_log(
            db,
            user_id=parse_id(session_data["user_id"]),
            action=DESTINATION_UPDATED_ACTION,
            resource_type="tracking_link",
            resource_id=str(link.id),
            details={
                "old": old_url,
                "new": new_url,
                "actor_name": actor_display_name(user),
            },
        )
    payload = _serialize_business_link(link, profile.display_name if profile else None)
    payload["offer_name"] = offer.name
    return await _with_site_match(db, business_id, payload)


@router.get("/offers/{offer_id}/links/{link_id}/destination-history")
async def get_destination_history(
    offer_id: str,
    link_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    _offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=parse_id(session_data["active_business_id"]),
    )
    rows = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.action == DESTINATION_UPDATED_ACTION,
                AuditLog.resource_type == "tracking_link",
                AuditLog.resource_id == str(link.id),
            )
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "destination_url": (row.details or {}).get("new"),
                "previous_url": (row.details or {}).get("old"),
                "actor_name": (row.details or {}).get("actor_name"),
            }
            for row in rows
        ]
    }


@router.get("/offers/{offer_id}/links/{link_id}/qr-code")
async def get_business_link_qr_code(
    offer_id: str,
    link_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    _offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=parse_id(session_data["active_business_id"]),
    )
    data = await QrCodeService().get_or_create(link.short_code)
    return png_response(data)


@router.get("/offers/{offer_id}/links/{link_id}/qr-code/download")
async def download_business_link_qr_code(
    offer_id: str,
    link_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    _offer, link = await _get_owned_link(
        db,
        offer_id=offer_id,
        link_id=link_id,
        business_id=parse_id(session_data["active_business_id"]),
    )
    data = await QrCodeService().get_or_create(link.short_code)
    return png_response(data, as_attachment=True, short_code=link.short_code)
