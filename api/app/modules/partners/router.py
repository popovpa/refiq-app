from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.core.ids import parse_id

from app.common.date_range import resolve_query_range
from app.core.database import get_db
from app.core.permissions import require_partner_role
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.partners.models import PartnerProfile, BusinessPartner
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink, TrackingLinkStatus
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.offers.service import (
    ACTIVE_ACCESS_STATUSES,
    apply_partner_offer_request,
    cr as conversion_rate,
    offer_category_filter,
    offer_public_fields,
    offer_stats,
    serialize_partner_application,
)
from app.modules.commissions.models import Commission
from app.modules.payouts.models import Payout
from app.modules.users.models import User
from app.modules.promotion.ownership import (
    OWN_OFFER_MARKETPLACE_STATUSES,
    assert_not_own_offer_for_partner_flow,
    is_own_offer,
    user_owned_business_ids,
)

router = APIRouter()

PROMOTION_PERIOD_DAYS = 7


async def _get_partner_profile(user_id: str, db: AsyncSession) -> PartnerProfile:
    result = await db.execute(
        select(PartnerProfile).where(PartnerProfile.user_id == parse_id(user_id))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner profile")
    return profile


def _empty_promotion() -> dict:
    return {
        "promotion_status": "NOT_STARTED",
        "active_links_count": 0,
        "total_links_count": 0,
        "partner_clicks": 0,
        "partner_conversions": 0,
        "partner_cr": 0.0,
    }


async def _partner_promotions(db: AsyncSession, partner_id: int, offer_ids: list[int]) -> dict[int, dict]:
    result = {offer_id: _empty_promotion() for offer_id in offer_ids}
    if not offer_ids:
        return result

    total_rows = (
        await db.execute(
            select(TrackingLink.offer_id, func.count(TrackingLink.id))
            .where(TrackingLink.partner_id == partner_id, TrackingLink.offer_id.in_(offer_ids))
            .group_by(TrackingLink.offer_id)
        )
    ).all()
    active_rows = (
        await db.execute(
            select(TrackingLink.offer_id, func.count(TrackingLink.id))
            .where(
                TrackingLink.partner_id == partner_id,
                TrackingLink.offer_id.in_(offer_ids),
                TrackingLink.status == TrackingLinkStatus.ACTIVE.value,
            )
            .group_by(TrackingLink.offer_id)
        )
    ).all()
    start = (datetime.now(timezone.utc) - timedelta(days=PROMOTION_PERIOD_DAYS - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    click_rows = (
        await db.execute(
            select(TrackingLink.offer_id, func.count(Click.id))
            .join(Click, Click.tracking_link_id == TrackingLink.id)
            .where(
                TrackingLink.partner_id == partner_id,
                TrackingLink.offer_id.in_(offer_ids),
                Click.created_at >= start,
            )
            .group_by(TrackingLink.offer_id)
        )
    ).all()
    conv_rows = (
        await db.execute(
            select(Conversion.offer_id, func.count(Conversion.id))
            .where(
                Conversion.partner_id == partner_id,
                Conversion.offer_id.in_(offer_ids),
                Conversion.created_at >= start,
            )
            .group_by(Conversion.offer_id)
        )
    ).all()

    totals = {offer_id: int(count) for offer_id, count in total_rows}
    actives = {offer_id: int(count) for offer_id, count in active_rows}
    clicks = {offer_id: int(count) for offer_id, count in click_rows}
    conversions = {offer_id: int(count) for offer_id, count in conv_rows}
    for offer_id in offer_ids:
        total = totals.get(offer_id, 0)
        active = actives.get(offer_id, 0)
        if active > 0:
            status = "ACTIVE"
        elif total > 0:
            status = "PAUSED"
        else:
            status = "NOT_STARTED"
        partner_clicks = clicks.get(offer_id, 0)
        partner_conversions = conversions.get(offer_id, 0)
        result[offer_id] = {
            "promotion_status": status,
            "active_links_count": active,
            "total_links_count": total,
            "partner_clicks": partner_clicks,
            "partner_conversions": partner_conversions,
            "partner_cr": conversion_rate(partner_clicks, partner_conversions),
        }
    return result


@router.get("/dashboard")
async def partner_dashboard(
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    days: int | None = Query(default=None, ge=1, le=366),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    date_range = resolve_query_range(date_from, date_to, timezone_name, days)

    offers_count = await db.scalar(
        select(func.count(OfferPartnerAccess.id)).where(
            OfferPartnerAccess.partner_id == profile.id,
            OfferPartnerAccess.status == "approved",
        )
    )
    links_count = await db.scalar(
        select(func.count(TrackingLink.id)).where(
            TrackingLink.partner_id == profile.id,
            TrackingLink.status == TrackingLinkStatus.ACTIVE.value,
        )
    )
    conversions_count = await db.scalar(
        select(func.count(Conversion.id)).where(
            Conversion.partner_id == profile.id,
            Conversion.created_at >= date_range.start,
            Conversion.created_at <= date_range.end,
        )
    )
    earnings = await db.scalar(
        select(func.coalesce(func.sum(Commission.amount), 0)).where(
            Commission.partner_id == profile.id,
            Commission.status.in_(["approved", "payable", "paid"]),
            Commission.created_at >= date_range.start,
            Commission.created_at <= date_range.end,
        )
    )
    pending_payout = await db.scalar(
        select(func.coalesce(func.sum(Commission.amount), 0)).where(
            Commission.partner_id == profile.id,
            Commission.status.in_(["approved", "payable"]),
        )
    )

    return {
        "active_offers": offers_count or 0,
        "active_links": links_count or 0,
        "has_offers": bool(offers_count),
        "total_conversions": conversions_count or 0,
        "total_earnings": float(earnings or 0),
        "pending_payout": float(pending_payout or 0),
        "from": date_range.start.isoformat(),
        "to": date_range.end.isoformat(),
        "timezone": date_range.timezone,
    }


class JoinOfferRequest(BaseModel):
    model_config = {"extra": "ignore"}


def _serialize_partner_offer(
    offer: Offer,
    partner_status: str | None,
    stats: dict | None = None,
    *,
    owned_business_ids: set[int] | None = None,
    rejection_reason: str | None = None,
) -> dict:
    payload = offer_public_fields(offer)
    payload["partner_status"] = partner_status
    payload["is_own_offer"] = bool(owned_business_ids and is_own_offer(offer, owned_business_ids))
    payload["rejection_reason"] = rejection_reason if partner_status == "rejected" else None
    if stats:
        payload.update(
            {
                "clicks": stats["clicks"],
                "conversions": stats["conversions"],
                "cr": stats["cr"],
                "epc": stats["epc"],
            }
        )
    return payload


@router.get("/offers")
async def partner_my_offers(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    owned_business_ids = await user_owned_business_ids(db, user_id)

    query = (
        select(OfferPartnerAccess, Offer)
        .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
        .where(OfferPartnerAccess.partner_id == profile.id)
        .order_by(OfferPartnerAccess.created_at.desc())
    )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))

    items = []
    for access, offer in result.all():
        stats = await offer_stats(db, offer.id, partner_id=profile.id)
        item = _serialize_partner_offer(
            offer,
            access.status,
            stats,
            owned_business_ids=owned_business_ids,
            rejection_reason=access.rejection_reason,
        )
        items.append(item)

    promotions = await _partner_promotions(db, profile.id, [item["id"] for item in items])
    for item in items:
        item.update(promotions.get(item["id"], _empty_promotion()))

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.get("/offers/marketplace")
async def partner_marketplace(
    q: str | None = None,
    category: str | None = None,
    geo: str | None = None,
    access_policy: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    owned_business_ids = await user_owned_business_ids(db, user_id)

    public_active = and_(Offer.status == "active", Offer.visibility == "public")
    if owned_business_ids:
        own_visible = and_(
            Offer.business_id.in_(owned_business_ids),
            Offer.status.in_(OWN_OFFER_MARKETPLACE_STATUSES),
        )
        visibility = or_(public_active, own_visible)
    else:
        visibility = public_active

    filters = [visibility]
    if q:
        filters.append(Offer.name.ilike(f"%{q.strip()}%"))
    if category:
        filters.append(offer_category_filter(category))
    if geo:
        filters.append(Offer.geo.ilike(f"%{geo.strip()}%"))
    if access_policy:
        filters.append(Offer.access_policy == access_policy)

    query = select(Offer).where(*filters).order_by(Offer.created_at.desc())
    total = await db.scalar(select(func.count(Offer.id)).where(*filters))
    offers = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    access_map = {}
    if offers:
        access_result = await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.partner_id == profile.id,
                OfferPartnerAccess.offer_id.in_([o.id for o in offers]),
            )
        )
        access_map = {a.offer_id: a for a in access_result.scalars().all()}

    items = []
    for offer in offers:
        stats = await offer_stats(db, offer.id)
        access = access_map.get(offer.id)
        items.append(
            _serialize_partner_offer(
                offer,
                access.status if access else None,
                stats,
                owned_business_ids=owned_business_ids,
                rejection_reason=access.rejection_reason if access else None,
            )
        )

    promotions = await _partner_promotions(db, profile.id, [offer.id for offer in offers])
    for item in items:
        item.update(promotions.get(item["id"], _empty_promotion()))

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.get("/offers/{offer_id}")
async def partner_offer_detail(
    offer_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    owned_business_ids = await user_owned_business_ids(db, session_data["user_id"])
    offer = (
        await db.execute(select(Offer).where(Offer.id == parse_id(offer_id)))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")

    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    own = is_own_offer(offer, owned_business_ids)
    public_active = offer.status == "active" and offer.visibility == "public"
    own_visible = own and offer.status in OWN_OFFER_MARKETPLACE_STATUSES
    access_visible = bool(access and access.status in {"approved", "pending"})
    if not public_active and not own_visible and not access_visible:
        raise NotFoundError("Offer")

    stats = await offer_stats(db, offer.id)
    mine = await offer_stats(db, offer.id, partner_id=profile.id) if access and access.status == "approved" else None
    payload = _serialize_partner_offer(
        offer,
        access.status if access else None,
        stats,
        owned_business_ids=owned_business_ids,
        rejection_reason=access.rejection_reason if access else None,
    )
    payload["my_stats"] = mine
    payload["application"] = serialize_partner_application(access) if access and not own else None
    payload["rejection_reason"] = access.rejection_reason if access and access.status == "rejected" and not own else None
    user = (
        await db.execute(select(User).where(User.id == profile.user_id))
    ).scalar_one_or_none()
    payload["partner_profile"] = {
        "name": profile.display_name,
        "email": user.email if user else None,
        "description": profile.description,
    }
    return payload


@router.post("/offers/{offer_id}/join")
async def join_offer(
    offer_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
    _data: JoinOfferRequest = Body(default_factory=JoinOfferRequest),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    owned_business_ids = await user_owned_business_ids(db, session_data["user_id"])
    offer = (
        await db.execute(select(Offer).where(Offer.id == parse_id(offer_id), Offer.status == "active"))
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    assert_not_own_offer_for_partner_flow(offer, owned_business_ids)
    if offer.access_policy == "invite_only":
        raise ForbiddenError("This offer is available by invitation only")

    existing = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    status = "approved" if offer.access_policy == "open" else "pending"

    if existing and existing.status in ACTIVE_ACCESS_STATUSES:
        raise ConflictError("Already requested access")
    access = apply_partner_offer_request(
        existing,
        offer_id=offer.id,
        partner_id=profile.id,
        status=status,
    )
    if existing is None:
        db.add(access)

    existing_bp = await db.execute(
        select(BusinessPartner).where(
            BusinessPartner.business_id == offer.business_id,
            BusinessPartner.partner_id == profile.id,
        )
    )
    if not existing_bp.scalar_one_or_none():
        db.add(
            BusinessPartner(
                business_id=offer.business_id,
                partner_id=profile.id,
                status="active" if status == "approved" else "pending",
            )
        )

    return {"status": status}


@router.post("/offers/{offer_id}/cancel-request")
async def cancel_offer_request(
    offer_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_partner_profile(session_data["user_id"], db)
    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == parse_id(offer_id),
                OfferPartnerAccess.partner_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if not access:
        raise NotFoundError("Application")
    if access.status != "pending":
        raise ForbiddenError("Only a pending request can be cancelled")
    access.status = "cancelled"
    return {"status": "cancelled"}


@router.get("/conversions")
async def list_partner_conversions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    filters = [Conversion.partner_id == profile.id]
    if date_from is not None and date_to is not None:
        date_range = resolve_query_range(date_from, date_to, timezone_name, None)
        filters.extend(
            [Conversion.created_at >= date_range.start, Conversion.created_at <= date_range.end]
        )

    total = await db.scalar(select(func.count(Conversion.id)).where(*filters))
    result = await db.execute(
        select(Conversion, Offer.name.label("offer_name"))
        .join(Offer, Conversion.offer_id == Offer.id)
        .where(*filters)
        .order_by(Conversion.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = [
        {
            "id": row.Conversion.id,
            "offer_id": row.Conversion.offer_id,
            "offer_name": row.offer_name,
            "click_id": row.Conversion.click_id,
            "external_id": row.Conversion.external_id,
            "amount": float(row.Conversion.amount),
            "currency": row.Conversion.currency,
            "commission_amount": float(row.Conversion.commission_amount),
            "status": row.Conversion.status,
            "converted_at": row.Conversion.converted_at.isoformat() if row.Conversion.converted_at else None,
            "created_at": row.Conversion.created_at.isoformat(),
        }
        for row in result.all()
    ]

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.get("/payouts")
async def list_partner_payouts(
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)

    available = await db.scalar(
        select(func.coalesce(func.sum(Commission.amount), 0)).where(
            Commission.partner_id == profile.id,
            Commission.status.in_(["approved", "payable"]),
        )
    )

    payouts_result = await db.execute(
        select(Payout)
        .where(Payout.partner_id == profile.id)
        .order_by(Payout.created_at.desc())
        .limit(50)
    )
    payouts = [
        {
            "id": p.id,
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        }
        for p in payouts_result.scalars().all()
    ]

    return {
        "available_amount": float(available or 0),
        "payouts": payouts,
    }


@router.get("/settings")
async def get_partner_settings(
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    return {
        "id": profile.id,
        "display_name": profile.display_name,
        "description": profile.description,
    }


@router.patch("/settings")
async def update_partner_settings(
    data: dict,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    user_id = session_data["user_id"]
    profile = await _get_partner_profile(user_id, db)
    allowed = {"display_name", "description"}
    for key, value in data.items():
        if key in allowed:
            setattr(profile, key, value)
    return {"status": "ok"}
