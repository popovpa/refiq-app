from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import as_float, iso
from app.common.enums import OfferStatus, SiteStatus
from app.core.exceptions import NotFoundError
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.campaigns.models import Campaign
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.creatives.models import Creative
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile
from app.modules.sdk.models import SdkScript
from app.modules.sites.models import Site
from app.modules.system.models import AuditLog
from app.modules.users.models import User


def _pages(total: int, per_page: int) -> int:
    return (total + per_page - 1) // per_page if per_page else 0


def _offset_page(items, total: int, page: int, per_page: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": _pages(total, per_page),
    }


async def _owner_email(db: AsyncSession, business_id: int) -> str | None:
    row = (
        await db.execute(
            select(User.email)
            .join(BusinessMembership, BusinessMembership.user_id == User.id)
            .where(
                BusinessMembership.business_id == business_id,
                BusinessMembership.permission_role == "owner",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def list_businesses(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    has_connected_sites: bool | None = None,
    has_active_offers: bool | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(Business)
    count_stmt = select(func.count(Business.id))
    filters = []
    if q:
        raw = q.strip()
        if raw.isdigit():
            filters.append(or_(Business.id == int(raw), func.lower(Business.name).like(f"%{raw.lower()}%")))
        elif "@" in raw:
            owner_ids = (
                select(BusinessMembership.business_id)
                .join(User, User.id == BusinessMembership.user_id)
                .where(func.lower(User.email) == raw.lower())
            )
            filters.append(Business.id.in_(owner_ids))
        else:
            filters.append(func.lower(Business.name).like(f"%{raw.lower()}%"))
    if status:
        filters.append(Business.status == status)
    if created_from:
        filters.append(Business.created_at >= created_from)
    if created_to:
        filters.append(Business.created_at <= created_to)
    if has_connected_sites:
        connected = (
            select(Site.business_id)
            .join(SdkScript, SdkScript.site_id == Site.id)
            .where(SdkScript.last_success_at.is_not(None))
            .distinct()
        )
        filters.append(Business.id.in_(connected))
    if has_active_offers:
        active = select(Offer.business_id).where(Offer.status == OfferStatus.ACTIVE.value).distinct()
        filters.append(Business.id.in_(active))
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Business.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()

    items = []
    for business in rows:
        owner = await _owner_email(db, business.id)
        sites = (await db.execute(select(func.count(Site.id)).where(Site.business_id == business.id))).scalar_one()
        offers = (await db.execute(select(func.count(Offer.id)).where(Offer.business_id == business.id))).scalar_one()
        partners = (
            await db.execute(
                select(func.count(func.distinct(OfferPartnerAccess.partner_id)))
                .select_from(OfferPartnerAccess)
                .join(Offer, Offer.id == OfferPartnerAccess.offer_id)
                .where(Offer.business_id == business.id, OfferPartnerAccess.status == "approved")
            )
        ).scalar_one()
        conversions = (
            await db.execute(
                select(func.count(Conversion.id)).where(
                    Conversion.business_id == business.id,
                    Conversion.created_at >= since,
                )
            )
        ).scalar_one()
        last_click = (
            await db.execute(
                select(func.max(Click.created_at))
                .select_from(Click)
                .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
                .join(Offer, Offer.id == TrackingLink.offer_id)
                .where(Offer.business_id == business.id)
            )
        ).scalar_one()
        last_conv = (
            await db.execute(
                select(func.max(Conversion.created_at)).where(Conversion.business_id == business.id)
            )
        ).scalar_one()
        last_activity = max([d for d in [last_click, last_conv, business.updated_at] if d], default=None)
        items.append(
            {
                "id": business.id,
                "name": business.name,
                "owner_email": owner,
                "sites": sites,
                "offers": offers,
                "partners": partners,
                "conversions_30d": conversions,
                "status": business.status,
                "last_activity_at": iso(last_activity),
                "created_at": iso(business.created_at),
            }
        )
    return _offset_page(items, total, page, per_page)


def _like_pattern(raw: str) -> str:
    escaped = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def lookup_businesses(
    db: AsyncSession,
    *,
    search: str | None = None,
    business_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    stmt = select(Business.id, Business.name)
    needle = (search or "").strip()
    if needle:
        stmt = stmt.where(func.lower(Business.name).like(_like_pattern(needle.lower()), escape="\\"))
    elif business_id:
        stmt = stmt.where(Business.id == business_id)
    rows = (await db.execute(stmt.order_by(Business.name.asc()).limit(limit))).all()
    return [{"id": row.id, "name": row.name} for row in rows]


async def get_business(db: AsyncSession, business_id: int) -> dict:
    business = await db.get(Business, business_id)
    if not business:
        raise NotFoundError("Business")
    owner = await _owner_email(db, business.id)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    sites = (await db.execute(select(func.count(Site.id)).where(Site.business_id == business.id))).scalar_one()
    offers = (await db.execute(select(func.count(Offer.id)).where(Offer.business_id == business.id))).scalar_one()
    partners = (
        await db.execute(
            select(func.count(func.distinct(OfferPartnerAccess.partner_id)))
            .select_from(OfferPartnerAccess)
            .join(Offer, Offer.id == OfferPartnerAccess.offer_id)
            .where(Offer.business_id == business.id, OfferPartnerAccess.status == "approved")
        )
    ).scalar_one()
    links = (
        await db.execute(
            select(func.count(TrackingLink.id))
            .select_from(TrackingLink)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .where(Offer.business_id == business.id)
        )
    ).scalar_one()
    clicks = (
        await db.execute(
            select(func.count(Click.id))
            .select_from(Click)
            .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .where(Offer.business_id == business.id, Click.created_at >= since)
        )
    ).scalar_one()
    conversions = (
        await db.execute(
            select(func.count(Conversion.id)).where(
                Conversion.business_id == business.id,
                Conversion.created_at >= since,
            )
        )
    ).scalar_one()
    recent_conversions = (
        await db.execute(
            select(Conversion).where(Conversion.business_id == business.id).order_by(Conversion.id.desc()).limit(8)
        )
    ).scalars().all()
    recent_links = (
        await db.execute(
            select(TrackingLink)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .where(Offer.business_id == business.id)
            .order_by(TrackingLink.id.desc())
            .limit(8)
        )
    ).scalars().all()
    admin_activity = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.resource_type.in_(["business", "offer", "site"]), AuditLog.resource_id.is_not(None))
            .order_by(AuditLog.id.desc())
            .limit(8)
        )
    ).scalars().all()
    return {
        "id": business.id,
        "name": business.name,
        "owner_email": owner,
        "status": business.status,
        "country": business.country,
        "currency": business.currency,
        "created_at": iso(business.created_at),
        "updated_at": iso(business.updated_at),
        "aggregates": {
            "sites": sites,
            "offers": offers,
            "partners": partners,
            "tracking_links": links,
            "clicks_30d": clicks,
            "conversions_30d": conversions,
        },
        "recent_conversions": [
            {
                "id": item.id,
                "rqcid": item.click_id,
                "status": item.status,
                "amount": as_float(item.amount),
                "created_at": iso(item.created_at),
            }
            for item in recent_conversions
        ],
        "recent_tracking_links": [
            {
                "id": item.id,
                "short_code": item.short_code,
                "status": item.status,
                "destination_url": item.destination_url,
            }
            for item in recent_links
        ],
        "admin_activity": [
            {
                "id": item.id,
                "action": item.action,
                "entity_type": item.resource_type,
                "entity_id": item.resource_id,
                "created_at": iso(item.created_at),
            }
            for item in admin_activity
        ],
        "sites": [
            {
                "id": site.id,
                "domain": site.domain,
                "status": site.status,
            }
            for site in (
                await db.execute(
                    select(Site).where(Site.business_id == business.id).order_by(Site.id.desc()).limit(50)
                )
            ).scalars().all()
        ],
        "offers": [
            {
                "id": offer.id,
                "name": offer.name,
                "status": offer.status,
            }
            for offer in (
                await db.execute(
                    select(Offer).where(Offer.business_id == business.id).order_by(Offer.id.desc()).limit(50)
                )
            ).scalars().all()
        ],
        "partners": [
            {
                "id": partner.id,
                "name": partner.display_name,
                "status": partner.status,
            }
            for partner in (
                await db.execute(
                    select(PartnerProfile)
                    .where(
                        PartnerProfile.id.in_(
                            select(OfferPartnerAccess.partner_id)
                            .join(Offer, Offer.id == OfferPartnerAccess.offer_id)
                            .where(Offer.business_id == business.id, OfferPartnerAccess.status == "approved")
                        )
                    )
                    .order_by(PartnerProfile.id.desc())
                    .limit(50)
                )
            ).scalars().all()
        ],
    }


async def list_partners(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(PartnerProfile, User.email).join(User, User.id == PartnerProfile.user_id)
    count_stmt = select(func.count(PartnerProfile.id)).select_from(PartnerProfile).join(User, User.id == PartnerProfile.user_id)
    filters = []
    if q:
        raw = q.strip().lower()
        filters.append(or_(func.lower(PartnerProfile.display_name).like(f"%{raw}%"), func.lower(User.email).like(f"%{raw}%")))
    if status:
        filters.append(PartnerProfile.status == status)
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(PartnerProfile.id.desc()).offset((page - 1) * per_page).limit(per_page)
        )
    ).all()
    items = []
    for partner, email in rows:
        offers = (
            await db.execute(
                select(func.count(OfferPartnerAccess.id)).where(
                    OfferPartnerAccess.partner_id == partner.id,
                    OfferPartnerAccess.status == "approved",
                )
            )
        ).scalar_one()
        links = (
            await db.execute(select(func.count(TrackingLink.id)).where(TrackingLink.partner_id == partner.id))
        ).scalar_one()
        clicks = (
            await db.execute(
                select(func.count(Click.id))
                .select_from(Click)
                .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
                .where(TrackingLink.partner_id == partner.id, Click.created_at >= since)
            )
        ).scalar_one()
        conversions = (
            await db.execute(
                select(func.count(Conversion.id)).where(
                    Conversion.partner_id == partner.id,
                    Conversion.created_at >= since,
                )
            )
        ).scalar_one()
        earnings = (
            await db.execute(
                select(func.coalesce(func.sum(Commission.amount), 0)).where(Commission.partner_id == partner.id)
            )
        ).scalar_one()
        items.append(
            {
                "id": partner.id,
                "name": partner.display_name,
                "email": email,
                "offers": offers,
                "tracking_links": links,
                "clicks_30d": clicks,
                "conversions_30d": conversions,
                "earnings": as_float(earnings),
                "status": partner.status,
            }
        )
    return _offset_page(items, total, page, per_page)


async def get_partner(db: AsyncSession, partner_id: int) -> dict:
    partner = await db.get(PartnerProfile, partner_id)
    if not partner:
        raise NotFoundError("Partner")
    user = await db.get(User, partner.user_id)
    offers = (
        await db.execute(
            select(Offer, OfferPartnerAccess.status)
            .join(OfferPartnerAccess, OfferPartnerAccess.offer_id == Offer.id)
            .where(OfferPartnerAccess.partner_id == partner.id)
            .order_by(Offer.id.desc())
            .limit(50)
        )
    ).all()
    links = (
        await db.execute(
            select(TrackingLink).where(TrackingLink.partner_id == partner.id).order_by(TrackingLink.id.desc()).limit(50)
        )
    ).scalars().all()
    conversions = (
        await db.execute(
            select(Conversion).where(Conversion.partner_id == partner.id).order_by(Conversion.id.desc()).limit(20)
        )
    ).scalars().all()
    return {
        "id": partner.id,
        "name": partner.display_name,
        "email": user.email if user else None,
        "description": partner.description,
        "status": partner.status,
        "created_at": iso(partner.created_at),
        "offers": [
            {"id": offer.id, "name": offer.name, "status": offer.status, "access_status": access_status}
            for offer, access_status in offers
        ],
        "tracking_links": [
            {
                "id": link.id,
                "short_code": link.short_code,
                "offer_id": link.offer_id,
                "status": link.status,
            }
            for link in links
        ],
        "conversions": [
            {
                "id": item.id,
                "rqcid": item.click_id,
                "status": item.status,
                "amount": as_float(item.amount),
                "created_at": iso(item.created_at),
            }
            for item in conversions
        ],
    }


async def list_sites(
    db: AsyncSession,
    *,
    business_id: int | None = None,
    status: str | None = None,
    sdk: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    stmt = (
        select(Site, Business.name, SdkScript.last_success_at)
        .join(Business, Business.id == Site.business_id)
        .outerjoin(SdkScript, SdkScript.site_id == Site.id)
    )
    count_stmt = select(func.count(Site.id))
    filters = []
    if business_id:
        filters.append(Site.business_id == business_id)
    if status:
        filters.append(Site.status == status)
    if sdk == "connected":
        filters.append(SdkScript.last_success_at.is_not(None))
    elif sdk == "not_connected":
        filters.append(SdkScript.last_success_at.is_(None))
    elif sdk == "no_activity":
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        filters.append(or_(SdkScript.last_success_at.is_(None), SdkScript.last_success_at < day_ago))
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.select_from(Site).outerjoin(SdkScript, SdkScript.site_id == Site.id).where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Site.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).all()
    items = [
        {
            "id": site.id,
            "domain": site.domain,
            "name": site.name,
            "business_id": site.business_id,
            "business_name": business_name,
            "sdk_status": "connected" if last_event else "not_detected",
            "last_event_at": iso(last_event),
            "events_24h": None,
            "status": site.status,
        }
        for site, business_name, last_event in rows
    ]
    return _offset_page(items, total, page, per_page)


async def get_site(db: AsyncSession, site_id: int) -> dict:
    row = (
        await db.execute(
            select(Site, Business.name, SdkScript.last_success_at, SdkScript.created_at)
            .join(Business, Business.id == Site.business_id)
            .outerjoin(SdkScript, SdkScript.site_id == Site.id)
            .where(Site.id == site_id)
        )
    ).first()
    if not row:
        raise NotFoundError("Site")
    site, business_name, last_event, first_event = row
    return {
        "id": site.id,
        "domain": site.domain,
        "name": site.name,
        "business_id": site.business_id,
        "business_name": business_name,
        "status": site.status,
        "site_key": site.site_key,
        "sdk_status": "connected" if last_event else "not_detected",
        "first_event_at": iso(first_event if last_event else None),
        "last_event_at": iso(last_event),
        "events_24h": None,
        "event_breakdown": None,
        "clickstream_available": False,
        "created_at": iso(site.created_at),
    }


async def list_offers(
    db: AsyncSession,
    *,
    business_id: int | None = None,
    partner_id: int | None = None,
    status: str | None = None,
    commission_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(Offer, Business.name).join(Business, Business.id == Offer.business_id)
    count_stmt = select(func.count(Offer.id))
    filters = []
    if business_id:
        filters.append(Offer.business_id == business_id)
    if partner_id:
        filters.append(
            Offer.id.in_(
                select(OfferPartnerAccess.offer_id).where(
                    OfferPartnerAccess.partner_id == partner_id,
                    OfferPartnerAccess.status == "approved",
                )
            )
        )
    if status:
        filters.append(Offer.status == status)
    if created_from:
        filters.append(Offer.created_at >= created_from)
    if created_to:
        filters.append(Offer.created_at <= created_to)
    if commission_type:
        from app.modules.offers.models import OfferCommissionRule

        filters.append(
            Offer.id.in_(select(OfferCommissionRule.offer_id).where(OfferCommissionRule.type == commission_type))
        )
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Offer.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).all()
    items = []
    for offer, business_name in rows:
        rule = offer.commission_rules[0] if offer.commission_rules else None
        partners = (
            await db.execute(
                select(func.count(OfferPartnerAccess.id)).where(
                    OfferPartnerAccess.offer_id == offer.id,
                    OfferPartnerAccess.status == "approved",
                )
            )
        ).scalar_one()
        links = (
            await db.execute(select(func.count(TrackingLink.id)).where(TrackingLink.offer_id == offer.id))
        ).scalar_one()
        conversions = (
            await db.execute(
                select(func.count(Conversion.id)).where(
                    Conversion.offer_id == offer.id,
                    Conversion.created_at >= since,
                )
            )
        ).scalar_one()
        items.append(
            {
                "id": offer.id,
                "name": offer.name,
                "business_id": offer.business_id,
                "business_name": business_name,
                "status": offer.status,
                "commission": {
                    "type": rule.type if rule else None,
                    "value": as_float(rule.value) if rule else None,
                    "currency": rule.currency if rule else offer.currency,
                },
                "attribution_window_days": offer.attribution_window_days,
                "partners": partners,
                "tracking_links": links,
                "conversions_30d": conversions,
            }
        )
    return _offset_page(items, total, page, per_page)


async def get_offer(db: AsyncSession, offer_id: int) -> dict:
    offer = await db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer")
    business = await db.get(Business, offer.business_id)
    rule = offer.commission_rules[0] if offer.commission_rules else None
    partners = [
        {"id": access.partner_id, "status": access.status, "source": access.source}
        for access in offer.partner_access
    ]
    links = (
        await db.execute(
            select(TrackingLink).where(TrackingLink.offer_id == offer.id).order_by(TrackingLink.id.desc()).limit(50)
        )
    ).scalars().all()
    creatives = (
        await db.execute(select(Creative).where(Creative.offer_id == offer.id).order_by(Creative.id.desc()).limit(20))
    ).scalars().all()
    conversions = (
        await db.execute(
            select(Conversion).where(Conversion.offer_id == offer.id).order_by(Conversion.id.desc()).limit(20)
        )
    ).scalars().all()
    return {
        "id": offer.id,
        "name": offer.name,
        "description": offer.description,
        "status": offer.status,
        "visibility": offer.visibility,
        "access_policy": offer.access_policy,
        "business_id": offer.business_id,
        "business_name": business.name if business else None,
        "category": offer.category,
        "geo": offer.geo,
        "conversion_type": offer.conversion_type,
        "attribution_window_days": offer.attribution_window_days,
        "allowed_traffic": offer.allowed_traffic,
        "forbidden_traffic": offer.forbidden_traffic,
        "partner_notes": offer.partner_notes,
        "commission": {
            "type": rule.type if rule else None,
            "value": as_float(rule.value) if rule else None,
            "currency": rule.currency if rule else offer.currency,
        },
        "partners": partners,
        "tracking_links": [
            {
                "id": link.id,
                "short_code": link.short_code,
                "partner_id": link.partner_id,
                "status": link.status,
                "destination_url": link.destination_url,
            }
            for link in links
        ],
        "creatives": [
            {"id": item.id, "type": item.type, "status": item.status, "title": item.title}
            for item in creatives
        ],
        "conversions": [
            {
                "id": item.id,
                "rqcid": item.click_id,
                "status": item.status,
                "amount": as_float(item.amount),
                "created_at": iso(item.created_at),
            }
            for item in conversions
        ],
        "created_at": iso(offer.created_at),
    }


async def list_tracking_links(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    stmt = (
        select(TrackingLink, Offer.name, Offer.business_id, Business.name, PartnerProfile.display_name, Campaign.name)
        .join(Offer, Offer.id == TrackingLink.offer_id)
        .join(Business, Business.id == Offer.business_id)
        .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
        .outerjoin(Campaign, Campaign.id == TrackingLink.campaign_id)
    )
    count_stmt = (
        select(func.count(TrackingLink.id))
        .select_from(TrackingLink)
        .join(Offer, Offer.id == TrackingLink.offer_id)
    )
    filters = []
    if q:
        raw = q.strip().lower()
        filters.append(TrackingLink.short_code == raw if len(raw) == 7 else func.lower(TrackingLink.short_code).like(f"{raw}%"))
    if status:
        filters.append(TrackingLink.status == status)
    if business_id:
        filters.append(Offer.business_id == business_id)
    if partner_id:
        filters.append(TrackingLink.partner_id == partner_id)
    if offer_id:
        filters.append(TrackingLink.offer_id == offer_id)
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(TrackingLink.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).all()
    items = []
    for link, offer_name, business_id, business_name, partner_name, campaign_name in rows:
        clicks = (await db.execute(select(func.count(Click.id)).where(Click.tracking_link_id == link.id))).scalar_one()
        conversions = (
            await db.execute(select(func.count(Conversion.id)).where(Conversion.tracking_link_id == link.id))
        ).scalar_one()
        last_click = (
            await db.execute(select(func.max(Click.created_at)).where(Click.tracking_link_id == link.id))
        ).scalar_one()
        items.append(
            {
                "id": link.id,
                "short_code": link.short_code,
                "offer_id": link.offer_id,
                "offer_name": offer_name,
                "business_id": business_id,
                "business_name": business_name,
                "partner_id": link.partner_id,
                "partner_name": partner_name,
                "campaign_id": link.campaign_id,
                "campaign_name": campaign_name,
                "destination_url": link.destination_url,
                "status": link.status,
                "clicks": clicks,
                "conversions": conversions,
                "last_click_at": iso(last_click),
            }
        )
    return _offset_page(items, total, page, per_page)


async def get_tracking_link(db: AsyncSession, link_id: int) -> dict:
    row = (
        await db.execute(
            select(TrackingLink, Offer, Business, PartnerProfile, Campaign)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .join(Business, Business.id == Offer.business_id)
            .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
            .outerjoin(Campaign, Campaign.id == TrackingLink.campaign_id)
            .where(TrackingLink.id == link_id)
        )
    ).first()
    if not row:
        raise NotFoundError("TrackingLink")
    link, offer, business, partner, campaign = row
    clicks = (await db.execute(select(func.count(Click.id)).where(Click.tracking_link_id == link.id))).scalar_one()
    conversions = (
        await db.execute(select(func.count(Conversion.id)).where(Conversion.tracking_link_id == link.id))
    ).scalar_one()
    last_click = (
        await db.execute(select(func.max(Click.created_at)).where(Click.tracking_link_id == link.id))
    ).scalar_one()
    return {
        "id": link.id,
        "short_code": link.short_code,
        "public_url": f"https://go.refiq.ru/{link.short_code}",
        "business_id": business.id,
        "business_name": business.name,
        "partner_id": partner.id,
        "partner_name": partner.display_name,
        "offer_id": offer.id,
        "offer_name": offer.name,
        "campaign_id": campaign.id if campaign else None,
        "campaign_name": campaign.name if campaign else None,
        "destination_url": link.destination_url,
        "status": link.status,
        "created_at": iso(link.created_at),
        "last_click_at": iso(last_click),
        "clicks_total": clicks,
        "conversions_total": conversions,
    }
