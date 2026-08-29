from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import as_float, encode_cursor, iso, keyset_before
from app.core.exceptions import NotFoundError
from app.modules.businesses.models import Business
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout, PayoutItem
from app.modules.postback.attempt import PostbackAttempt
from app.modules.sites.domain import hostname_from_url
from app.modules.sites.models import Site


def _cursor_page(rows, limit: int, created_at_attr: str = "created_at"):
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        stamp = getattr(last, created_at_attr)
        next_cursor = encode_cursor(stamp, last.id)
    return rows, next_cursor, has_more


async def _site_for_url(db: AsyncSession, business_id: int | None, url: str | None) -> dict | None:
    host = hostname_from_url(url)
    if not host or not business_id:
        return None
    site = (
        await db.execute(select(Site).where(Site.business_id == business_id, Site.domain == host))
    ).scalar_one_or_none()
    if not site:
        return None
    return {"id": site.id, "domain": site.domain}


async def list_clicks(
    db: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 50,
    rqcid: str | None = None,
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
) -> dict:
    stmt = (
        select(Click, TrackingLink, Offer, Business, PartnerProfile)
        .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
        .join(Offer, Offer.id == TrackingLink.offer_id)
        .join(Business, Business.id == Offer.business_id)
        .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
        .where(keyset_before(Click.created_at, Click.id, cursor))
        .order_by(Click.created_at.desc(), Click.id.desc())
        .limit(limit + 1)
    )
    if rqcid:
        stmt = stmt.where(Click.rqcid == rqcid)
    if business_id:
        stmt = stmt.where(Offer.business_id == business_id)
    if partner_id:
        stmt = stmt.where(TrackingLink.partner_id == partner_id)
    if offer_id:
        stmt = stmt.where(TrackingLink.offer_id == offer_id)
    rows = (await db.execute(stmt)).all()
    sliced, next_cursor, has_more = _cursor_page([row[0] for row in rows], limit)
    by_id = {row[0].id: row for row in rows}
    items = []
    for click in sliced:
        click, link, offer, business, partner = by_id[click.id]
        site = await _site_for_url(db, offer.business_id, link.destination_url)
        items.append(
            {
                "id": click.id,
                "created_at": iso(click.created_at),
                "rqcid": click.rqcid,
                "short_code": link.short_code,
                "tracking_link_id": link.id,
                "offer_id": offer.id,
                "offer_name": offer.name,
                "partner_id": partner.id,
                "partner_name": partner.display_name,
                "business_id": business.id,
                "site_id": site["id"] if site else None,
                "site_domain": site["domain"] if site else None,
                "source": link.traffic_source,
                "country": None,
            }
        )
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_click(db: AsyncSession, rqcid: str) -> dict:
    row = (
        await db.execute(
            select(Click, TrackingLink, Offer, Business, PartnerProfile)
            .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .join(Business, Business.id == Offer.business_id)
            .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
            .where(Click.rqcid == rqcid)
        )
    ).first()
    if not row:
        raise NotFoundError("Click")
    click, link, offer, business, partner = row
    site = await _site_for_url(db, offer.business_id, link.destination_url)
    return {
        "id": click.id,
        "rqcid": click.rqcid,
        "created_at": iso(click.created_at),
        "tracking_link_id": link.id,
        "short_code": link.short_code,
        "offer_id": offer.id,
        "offer_name": offer.name,
        "partner_id": partner.id,
        "partner_name": partner.display_name,
        "business_id": business.id,
        "business_name": business.name,
        "destination_url": link.destination_url,
        "referrer": click.referer,
        "source": link.traffic_source,
        "country": None,
        "device": None,
        "site": site,
        "technical": {
            "client_ip": click.client_ip,
            "user_agent": click.user_agent,
        },
    }


async def list_conversions(
    db: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 50,
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
    status: str | None = None,
) -> dict:
    stmt = (
        select(Conversion, Business.name, Offer.name, PartnerProfile.display_name)
        .join(Business, Business.id == Conversion.business_id)
        .join(Offer, Offer.id == Conversion.offer_id)
        .join(PartnerProfile, PartnerProfile.id == Conversion.partner_id)
        .where(keyset_before(Conversion.created_at, Conversion.id, cursor))
        .order_by(Conversion.created_at.desc(), Conversion.id.desc())
        .limit(limit + 1)
    )
    if business_id:
        stmt = stmt.where(Conversion.business_id == business_id)
    if partner_id:
        stmt = stmt.where(Conversion.partner_id == partner_id)
    if offer_id:
        stmt = stmt.where(Conversion.offer_id == offer_id)
    if status:
        stmt = stmt.where(Conversion.status == status)
    rows = (await db.execute(stmt)).all()
    sliced = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = encode_cursor(sliced[-1][0].created_at, sliced[-1][0].id) if has_more and sliced else None
    items = [
        {
            "id": conversion.id,
            "created_at": iso(conversion.created_at),
            "rqcid": conversion.click_id,
            "business_id": conversion.business_id,
            "business_name": business_name,
            "offer_id": conversion.offer_id,
            "offer_name": offer_name,
            "partner_id": conversion.partner_id,
            "partner_name": partner_name,
            "value": as_float(conversion.amount),
            "commission": as_float(conversion.commission_amount),
            "status": conversion.status,
        }
        for conversion, business_name, offer_name, partner_name in sliced
    ]
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_conversion(db: AsyncSession, conversion_id: int) -> dict:
    conversion = await db.get(Conversion, conversion_id)
    if not conversion:
        raise NotFoundError("Conversion")
    business = await db.get(Business, conversion.business_id)
    offer = await db.get(Offer, conversion.offer_id)
    partner = await db.get(PartnerProfile, conversion.partner_id)
    commission = (
        await db.execute(select(Commission).where(Commission.conversion_id == conversion.id))
    ).scalar_one_or_none()
    payout_id = None
    payout_status = None
    if commission:
        payout_id = (
            await db.execute(select(PayoutItem.payout_id).where(PayoutItem.commission_id == commission.id))
        ).scalar_one_or_none()
        if payout_id:
            payout = await db.get(Payout, payout_id)
            payout_status = payout.status if payout else None
    postback = (
        await db.execute(
            select(PostbackAttempt)
            .where(PostbackAttempt.conversion_id == conversion.id)
            .order_by(PostbackAttempt.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {
        "id": conversion.id,
        "rqcid": conversion.click_id,
        "business_id": conversion.business_id,
        "business_name": business.name if business else None,
        "offer_id": conversion.offer_id,
        "offer_name": offer.name if offer else None,
        "partner_id": conversion.partner_id,
        "partner_name": partner.display_name if partner else None,
        "external_id": conversion.external_id,
        "amount": as_float(conversion.amount),
        "currency": conversion.currency,
        "commission_amount": as_float(conversion.commission_amount),
        "commission_id": commission.id if commission else None,
        "attribution_result": "ATTRIBUTED",
        "postback_id": postback.id if postback else None,
        "postback_result": postback.result if postback else None,
        "created_at": iso(conversion.created_at),
        "status": conversion.status,
        "payout_id": payout_id,
        "payout_status": payout_status,
    }


async def list_postbacks(
    db: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 50,
    result: str | None = None,
    business_id: int | None = None,
) -> dict:
    stmt = (
        select(PostbackAttempt, Business.name)
        .outerjoin(Business, Business.id == PostbackAttempt.business_id)
        .where(keyset_before(PostbackAttempt.received_at, PostbackAttempt.id, cursor))
        .order_by(PostbackAttempt.received_at.desc(), PostbackAttempt.id.desc())
        .limit(limit + 1)
    )
    if result:
        stmt = stmt.where(PostbackAttempt.result == result)
    if business_id:
        stmt = stmt.where(PostbackAttempt.business_id == business_id)
    rows = (await db.execute(stmt)).all()
    sliced = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = (
        encode_cursor(sliced[-1][0].received_at, sliced[-1][0].id) if has_more and sliced else None
    )
    items = [
        {
            "id": attempt.id,
            "received_at": iso(attempt.received_at),
            "business_id": attempt.business_id,
            "business_name": business_name,
            "rqcid": attempt.rqcid,
            "result": attempt.result,
            "reason_code": attempt.reason_code,
            "conversion_id": attempt.conversion_id,
        }
        for attempt, business_name in sliced
    ]
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def list_commissions(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    partner_id: int | None = None,
    business_id: int | None = None,
) -> dict:
    stmt = (
        select(Commission, PartnerProfile.display_name, Offer.name, Conversion.id)
        .join(PartnerProfile, PartnerProfile.id == Commission.partner_id)
        .join(Conversion, Conversion.id == Commission.conversion_id)
        .join(Offer, Offer.id == Conversion.offer_id)
    )
    count_stmt = select(func.count(Commission.id))
    filters = []
    if status:
        filters.append(Commission.status == status)
    if partner_id:
        filters.append(Commission.partner_id == partner_id)
    if business_id:
        filters.append(Commission.business_id == business_id)
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Commission.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).all()
    items = []
    for commission, partner_name, offer_name, conversion_id in rows:
        payout_id = (
            await db.execute(select(PayoutItem.payout_id).where(PayoutItem.commission_id == commission.id))
        ).scalar_one_or_none()
        items.append(
            {
                "id": commission.id,
                "partner_id": commission.partner_id,
                "partner_name": partner_name,
                "conversion_id": conversion_id,
                "offer_name": offer_name,
                "amount": as_float(commission.amount),
                "currency": commission.currency,
                "status": commission.status,
                "payout_id": payout_id,
            }
        )
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


async def get_commission(db: AsyncSession, commission_id: int) -> dict:
    commission = await db.get(Commission, commission_id)
    if not commission:
        raise NotFoundError("Commission")
    partner = await db.get(PartnerProfile, commission.partner_id)
    conversion = await db.get(Conversion, commission.conversion_id)
    offer = await db.get(Offer, conversion.offer_id) if conversion else None
    payout_id = (
        await db.execute(select(PayoutItem.payout_id).where(PayoutItem.commission_id == commission.id))
    ).scalar_one_or_none()
    return {
        "id": commission.id,
        "partner_id": commission.partner_id,
        "partner_name": partner.display_name if partner else None,
        "conversion_id": commission.conversion_id,
        "offer_id": offer.id if offer else None,
        "offer_name": offer.name if offer else None,
        "rqcid": conversion.click_id if conversion else None,
        "amount": as_float(commission.amount),
        "currency": commission.currency,
        "status": commission.status,
        "payout_id": payout_id,
        "created_at": iso(commission.created_at),
    }


async def list_payouts(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    partner_id: int | None = None,
) -> dict:
    stmt = select(Payout, PartnerProfile.display_name).join(
        PartnerProfile, PartnerProfile.id == Payout.partner_id
    )
    count_stmt = select(func.count(Payout.id))
    if status:
        stmt = stmt.where(Payout.status == status)
        count_stmt = count_stmt.where(Payout.status == status)
    if partner_id:
        stmt = stmt.where(Payout.partner_id == partner_id)
        count_stmt = count_stmt.where(Payout.partner_id == partner_id)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(Payout.id.desc()).offset((page - 1) * per_page).limit(per_page))
    ).all()
    items = [
        {
            "id": payout.id,
            "partner_id": payout.partner_id,
            "partner_name": partner_name,
            "amount": as_float(payout.amount),
            "currency": payout.currency,
            "status": payout.status,
            "period": iso(payout.created_at),
            "paid_at": iso(payout.paid_at),
        }
        for payout, partner_name in rows
    ]
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


async def get_payout(db: AsyncSession, payout_id: int) -> dict:
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise NotFoundError("Payout")
    partner = await db.get(PartnerProfile, payout.partner_id)
    items = []
    for item in payout.items:
        commission = await db.get(Commission, item.commission_id)
        items.append(
            {
                "id": item.id,
                "commission_id": item.commission_id,
                "conversion_id": commission.conversion_id if commission else None,
                "amount": as_float(item.amount),
            }
        )
    return {
        "id": payout.id,
        "partner_id": payout.partner_id,
        "partner_name": partner.display_name if partner else None,
        "amount": as_float(payout.amount),
        "currency": payout.currency,
        "status": payout.status,
        "created_at": iso(payout.created_at),
        "paid_at": iso(payout.paid_at),
        "items": items,
    }


async def list_audit(
    db: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 50,
    admin_user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict:
    from app.admin.audit.models import AdminAuditEvent
    from app.admin.auth.models import AdminUser

    stmt = (
        select(AdminAuditEvent, AdminUser.email)
        .join(AdminUser, AdminUser.id == AdminAuditEvent.admin_user_id)
        .where(keyset_before(AdminAuditEvent.created_at, AdminAuditEvent.id, cursor))
        .order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc())
        .limit(limit + 1)
    )
    if admin_user_id:
        stmt = stmt.where(AdminAuditEvent.admin_user_id == admin_user_id)
    if action:
        stmt = stmt.where(AdminAuditEvent.action == action)
    if entity_type:
        stmt = stmt.where(AdminAuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AdminAuditEvent.entity_id == str(entity_id))
    rows = (await db.execute(stmt)).all()
    sliced = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = encode_cursor(sliced[-1][0].created_at, sliced[-1][0].id) if has_more and sliced else None
    items = [
        {
            "id": event.id,
            "admin_user_id": event.admin_user_id,
            "admin_email": email,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "reason": event.reason,
            "details": event.details,
            "created_at": iso(event.created_at),
        }
        for event, email in sliced
    ]
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
