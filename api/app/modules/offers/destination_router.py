from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import DestinationStatus, DestinationType
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_business_role, require_partner_role
from app.modules.offers.destination_compliance import BETTING_CATEGORIES
from app.modules.offers.destination_service import (
    create_destination,
    disable_destination,
    list_destinations,
    serialize_destination,
    update_destination,
)
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.offers.service import ACTIVE_ACCESS_STATUSES
from app.modules.partners.models import PartnerProfile
from app.modules.promotion.ownership import (
    OWN_OFFER_MARKETPLACE_STATUSES,
    is_own_offer,
    require_offer_for_business,
    user_owned_business_ids,
)

business_router = APIRouter()
partner_router = APIRouter()


class CreateDestinationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=500)
    type: DestinationType = DestinationType.LANDING
    image_url: str | None = None
    is_primary: bool = False


class UpdateDestinationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=500)
    type: DestinationType | None = None
    image_url: str | None = None
    status: DestinationStatus | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None
    replacement_primary_id: int | None = None


async def _partner_profile(db: AsyncSession, user_id: str) -> PartnerProfile:
    profile = (
        await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id)))
    ).scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


async def _visible_partner_offer(db: AsyncSession, offer_id: str, user_id: str, profile: PartnerProfile) -> Offer:
    offer = (await db.execute(select(Offer).where(Offer.id == parse_id(offer_id)))).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    owned = await user_owned_business_ids(db, user_id)
    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    own = is_own_offer(offer, owned)
    public_active = offer.status == "active" and offer.visibility == "public"
    own_visible = own and offer.status in OWN_OFFER_MARKETPLACE_STATUSES
    access_visible = bool(access and access.status in ACTIVE_ACCESS_STATUSES)
    if not public_active and not own_visible and not access_visible:
        raise NotFoundError("Offer")
    return offer


@business_router.get("/{offer_id}/destinations")
async def business_list_destinations(
    offer_id: str,
    status: str | None = None,
    type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await require_offer_for_business(db, parse_id(offer_id), parse_id(session_data["active_business_id"]))
    return await list_destinations(
        db,
        offer,
        status=status,
        destination_type=type,
        page=page,
        per_page=per_page,
    )


@business_router.post("/{offer_id}/destinations")
async def business_create_destination(
    offer_id: str,
    data: CreateDestinationRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await require_offer_for_business(db, parse_id(offer_id), parse_id(session_data["active_business_id"]))
    destination, _created = await create_destination(
        db,
        offer,
        title=data.title,
        url=data.url,
        destination_type=data.type.value,
        image_url=data.image_url,
        is_primary=data.is_primary,
    )
    return serialize_destination(destination)


@business_router.patch("/{offer_id}/destinations/{destination_id}")
async def business_update_destination(
    offer_id: str,
    destination_id: str,
    data: UpdateDestinationRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await require_offer_for_business(db, parse_id(offer_id), parse_id(session_data["active_business_id"]))
    changes = data.model_dump(exclude_unset=True)
    if "type" in changes and changes["type"] is not None:
        changes["type"] = changes["type"].value
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    destination, warning = await update_destination(db, offer, parse_id(destination_id), changes)
    payload = serialize_destination(destination)
    if warning:
        payload["warning"] = warning
        payload["snapshots_unchanged"] = True
    if "url" in changes and (offer.category or "").upper() in BETTING_CATEGORIES:
        payload["compliance_review_required"] = True
    return payload


@business_router.delete("/{offer_id}/destinations/{destination_id}")
async def business_disable_destination(
    offer_id: str,
    destination_id: str,
    replacement_primary_id: int | None = None,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await require_offer_for_business(db, parse_id(offer_id), parse_id(session_data["active_business_id"]))
    destination = await disable_destination(
        db,
        offer,
        parse_id(destination_id),
        replacement_primary_id,
    )
    return serialize_destination(destination)


@partner_router.get("/{offer_id}/destinations")
async def partner_list_destinations(
    offer_id: str,
    type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _partner_profile(db, session_data["user_id"])
    offer = await _visible_partner_offer(db, offer_id, session_data["user_id"], profile)
    return await list_destinations(
        db,
        offer,
        destination_type=type,
        page=page,
        per_page=per_page,
        public=True,
    )
