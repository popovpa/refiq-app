from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.offers.service import cr as conversion_rate
from app.modules.partners.models import BusinessPartner, PartnerProfile
from app.modules.postback.credential_service import PostbackCredentialService
from app.modules.sdk.service import SdkCredentialService
from app.modules.users.models import User


def _period_start(days: int, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return (current - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _day_key(value) -> str:
    text = str(value)
    return text[:10]


async def build_business_dashboard(db: AsyncSession, business_id: int, days: int = 7) -> dict:
    now = datetime.now(timezone.utc)
    start = _period_start(days, now=now)
    previous_start = start - timedelta(days=days)

    offer_ids = list(
        (
            await db.execute(select(Offer.id).where(Offer.business_id == business_id))
        ).scalars()
    )
    active_offers = int(
        await db.scalar(
            select(func.count(Offer.id)).where(Offer.business_id == business_id, Offer.status == "active")
        )
        or 0
    )
    active_partners = int(
        await db.scalar(
            select(func.count(BusinessPartner.id)).where(
                BusinessPartner.business_id == business_id,
                BusinessPartner.status == "active",
            )
        )
        or 0
    )

    async def conversion_count(since: datetime, until: datetime | None = None, statuses: list[str] | None = None) -> int:
        filters = [Conversion.business_id == business_id, Conversion.created_at >= since]
        if until is not None:
            filters.append(Conversion.created_at < until)
        if statuses:
            filters.append(Conversion.status.in_(statuses))
        return int(await db.scalar(select(func.count(Conversion.id)).where(*filters)) or 0)

    async def conversion_sum(since: datetime, until: datetime | None = None, statuses: list[str] | None = None) -> float:
        filters = [Conversion.business_id == business_id, Conversion.created_at >= since]
        if until is not None:
            filters.append(Conversion.created_at < until)
        if statuses:
            filters.append(Conversion.status.in_(statuses))
        return float(
            await db.scalar(select(func.coalesce(func.sum(Conversion.amount), 0)).where(*filters)) or 0
        )

    conversions = await conversion_count(start)
    conversions_prev = await conversion_count(previous_start, start)
    sales = await conversion_sum(start, statuses=["approved", "paid"])
    sales_prev = await conversion_sum(previous_start, start, statuses=["approved", "paid"])
    approved = await conversion_count(start, statuses=["approved", "paid"])
    pending_conversions = await conversion_count(start, statuses=["pending"])
    commissions = float(
        await db.scalar(
            select(func.coalesce(func.sum(Conversion.commission_amount), 0)).where(
                Conversion.business_id == business_id,
                Conversion.created_at >= start,
                Conversion.status.in_(["approved", "paid"]),
            )
        )
        or 0
    )
    clicks = 0
    if offer_ids:
        clicks = int(
            await db.scalar(
                select(func.count(Click.id))
                .select_from(Click)
                .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
                .where(TrackingLink.offer_id.in_(offer_ids), Click.created_at >= start)
            )
            or 0
        )
    payout_pending = float(
        await db.scalar(
            select(func.coalesce(func.sum(Commission.amount), 0)).where(
                Commission.business_id == business_id,
                Commission.status == "pending",
            )
        )
        or 0
    )

    timeseries = await _timeseries(db, business_id, start, days)
    recent_conversions = await _recent_conversions(db, business_id, start)
    top_offers = await _top_offers(db, business_id, offer_ids, start)
    top_partners = await _top_partners(db, business_id, offer_ids, start)
    attention = await _attention(
        db,
        business_id=business_id,
        start=start,
        pending_conversions=pending_conversions,
        active_offers=active_offers,
    )
    postback = await PostbackCredentialService(db).get_status(business_id)
    sdk = await SdkCredentialService(db).get_status(business_id)
    if postback.integration_status != "connected" and len(attention) < 5:
        attention.append(
            {
                "key": "postback",
                "title": "Postback ещё не подключён"
                if postback.integration_status == "not_configured"
                else "Интеграция требует внимания",
                "detail": "Настройте Postback / S2S, чтобы принимать конверсии с backend.",
                "href": "/business/settings",
            }
        )
        attention = attention[:5]

    return {
        "period_days": days,
        "kpis": {
            "active_offers": active_offers,
            "active_partners": active_partners,
            "conversions": conversions,
            "conversions_change": _pct_change(conversions, conversions_prev),
            "sales": round(sales, 2),
            "sales_change": _pct_change(sales, sales_prev),
            "cr": conversion_rate(clicks, conversions),
            "commissions": round(commissions, 2),
        },
        "timeseries": timeseries,
        "recent_conversions": recent_conversions,
        "attention": attention,
        "top_offers": top_offers,
        "top_partners": top_partners,
        "funnel": {
            "clicks": clicks,
            "conversions": conversions,
            "conversion_rate": conversion_rate(clicks, conversions),
            "approved": approved,
            "approved_rate": conversion_rate(conversions, approved) if conversions else 0.0,
            "payout_pending": round(payout_pending, 2),
        },
        "integrations": {
            "postback": postback.integration_status,
            "sdk": sdk.integration_status,
        },
    }


async def _timeseries(db: AsyncSession, business_id: int, start: datetime, days: int) -> list[dict]:
    conv_rows = (
        await db.execute(
            select(
                func.date(Conversion.created_at),
                func.count(Conversion.id),
            )
            .where(Conversion.business_id == business_id, Conversion.created_at >= start)
            .group_by(func.date(Conversion.created_at))
        )
    ).all()
    sales_rows = (
        await db.execute(
            select(
                func.date(Conversion.created_at),
                func.coalesce(func.sum(Conversion.amount), 0),
            )
            .where(
                Conversion.business_id == business_id,
                Conversion.created_at >= start,
                Conversion.status.in_(["approved", "paid"]),
            )
            .group_by(func.date(Conversion.created_at))
        )
    ).all()
    conv_map = {_day_key(day): int(count) for day, count in conv_rows}
    sales_map = {_day_key(day): float(total) for day, total in sales_rows}
    series = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date().isoformat()
        series.append(
            {
                "date": day,
                "conversions": conv_map.get(day, 0),
                "sales": round(sales_map.get(day, 0.0), 2),
            }
        )
    return series


async def _recent_conversions(db: AsyncSession, business_id: int, start: datetime) -> list[dict]:
    rows = (
        await db.execute(
            select(Conversion, Offer.name, PartnerProfile.display_name, User.email)
            .join(Offer, Conversion.offer_id == Offer.id)
            .join(PartnerProfile, Conversion.partner_id == PartnerProfile.id)
            .join(User, PartnerProfile.user_id == User.id)
            .where(Conversion.business_id == business_id, Conversion.created_at >= start)
            .order_by(Conversion.created_at.desc())
            .limit(5)
        )
    ).all()
    return [
        {
            "id": conversion.id,
            "offer_id": conversion.offer_id,
            "offer_name": offer_name,
            "partner_name": partner_name or email,
            "amount": float(conversion.amount),
            "status": conversion.status,
            "created_at": conversion.created_at.isoformat() if conversion.created_at else None,
        }
        for conversion, offer_name, partner_name, email in rows
    ]


async def _top_offers(db: AsyncSession, business_id: int, offer_ids: list[int], start: datetime) -> list[dict]:
    if not offer_ids:
        return []
    conv_rows = (
        await db.execute(
            select(
                Conversion.offer_id,
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.amount), 0),
                func.coalesce(func.sum(Conversion.commission_amount), 0),
            )
            .where(Conversion.business_id == business_id, Conversion.created_at >= start)
            .group_by(Conversion.offer_id)
        )
    ).all()
    sales_rows = (
        await db.execute(
            select(Conversion.offer_id, func.coalesce(func.sum(Conversion.amount), 0))
            .where(
                Conversion.business_id == business_id,
                Conversion.created_at >= start,
                Conversion.status.in_(["approved", "paid"]),
            )
            .group_by(Conversion.offer_id)
        )
    ).all()
    click_rows = (
        await db.execute(
            select(TrackingLink.offer_id, func.count(Click.id))
            .join(Click, Click.tracking_link_id == TrackingLink.id)
            .where(TrackingLink.offer_id.in_(offer_ids), Click.created_at >= start)
            .group_by(TrackingLink.offer_id)
        )
    ).all()
    partner_rows = (
        await db.execute(
            select(OfferPartnerAccess.offer_id, func.count(OfferPartnerAccess.id))
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(Offer.business_id == business_id, OfferPartnerAccess.status == "approved")
            .group_by(OfferPartnerAccess.offer_id)
        )
    ).all()
    names = {
        offer_id: name
        for offer_id, name in (
            await db.execute(select(Offer.id, Offer.name).where(Offer.business_id == business_id))
        ).all()
    }
    conversions = {offer_id: int(count) for offer_id, count, _amount, _comm in conv_rows}
    commissions = {offer_id: float(comm) for offer_id, _count, _amount, comm in conv_rows}
    sales = {offer_id: float(total) for offer_id, total in sales_rows}
    clicks = {offer_id: int(count) for offer_id, count in click_rows}
    partners = {offer_id: int(count) for offer_id, count in partner_rows}
    ranked_ids = [offer_id for offer_id, count, *_ in conv_rows if count > 0]
    ranked_ids.sort(key=lambda offer_id: (sales.get(offer_id, 0.0), conversions.get(offer_id, 0)), reverse=True)
    items = []
    for offer_id in ranked_ids[:5]:
        items.append(
            {
                "id": offer_id,
                "name": names.get(offer_id, "Оффер"),
                "partners": partners.get(offer_id, 0),
                "conversions": conversions.get(offer_id, 0),
                "cr": conversion_rate(clicks.get(offer_id, 0), conversions.get(offer_id, 0)),
                "sales": round(sales.get(offer_id, 0.0), 2),
                "commissions": round(commissions.get(offer_id, 0.0), 2),
            }
        )
    return items


async def _top_partners(db: AsyncSession, business_id: int, offer_ids: list[int], start: datetime) -> list[dict]:
    conv_rows = (
        await db.execute(
            select(
                Conversion.partner_id,
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.amount), 0),
                func.coalesce(func.sum(Conversion.commission_amount), 0),
            )
            .where(Conversion.business_id == business_id, Conversion.created_at >= start)
            .group_by(Conversion.partner_id)
        )
    ).all()
    sales_rows = (
        await db.execute(
            select(Conversion.partner_id, func.coalesce(func.sum(Conversion.amount), 0))
            .where(
                Conversion.business_id == business_id,
                Conversion.created_at >= start,
                Conversion.status.in_(["approved", "paid"]),
            )
            .group_by(Conversion.partner_id)
        )
    ).all()
    click_rows = []
    if offer_ids:
        click_rows = (
            await db.execute(
                select(TrackingLink.partner_id, func.count(Click.id))
                .join(Click, Click.tracking_link_id == TrackingLink.id)
                .where(TrackingLink.offer_id.in_(offer_ids), Click.created_at >= start)
                .group_by(TrackingLink.partner_id)
            )
        ).all()
    offer_rows = (
        await db.execute(
            select(OfferPartnerAccess.partner_id, func.count(OfferPartnerAccess.id))
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(Offer.business_id == business_id, OfferPartnerAccess.status == "approved")
            .group_by(OfferPartnerAccess.partner_id)
        )
    ).all()
    conversions = {partner_id: int(count) for partner_id, count, _amount, _comm in conv_rows}
    commissions = {partner_id: float(comm) for partner_id, _count, _amount, comm in conv_rows}
    sales = {partner_id: float(total) for partner_id, total in sales_rows}
    clicks = {partner_id: int(count) for partner_id, count in click_rows}
    offers = {partner_id: int(count) for partner_id, count in offer_rows}
    ranked_ids = [partner_id for partner_id, count, *_ in conv_rows if count > 0]
    ranked_ids.sort(key=lambda partner_id: (sales.get(partner_id, 0.0), conversions.get(partner_id, 0)), reverse=True)
    ranked_ids = ranked_ids[:5]
    if not ranked_ids:
        return []
    name_rows = (
        await db.execute(
            select(PartnerProfile.id, PartnerProfile.display_name, User.email)
            .join(User, PartnerProfile.user_id == User.id)
            .where(PartnerProfile.id.in_(ranked_ids))
        )
    ).all()
    names = {partner_id: display_name or email for partner_id, display_name, email in name_rows}
    return [
        {
            "id": partner_id,
            "name": names.get(partner_id, "Партнёр"),
            "offers": offers.get(partner_id, 0),
            "conversions": conversions.get(partner_id, 0),
            "cr": conversion_rate(clicks.get(partner_id, 0), conversions.get(partner_id, 0)),
            "sales": round(sales.get(partner_id, 0.0), 2),
            "commissions": round(commissions.get(partner_id, 0.0), 2),
        }
        for partner_id in ranked_ids
    ]


async def _attention(
    db: AsyncSession,
    *,
    business_id: int,
    start: datetime,
    pending_conversions: int,
    active_offers: int,
) -> list[dict]:
    items: list[dict] = []
    pending_apps = int(
        await db.scalar(
            select(func.count(OfferPartnerAccess.id))
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(Offer.business_id == business_id, OfferPartnerAccess.status == "pending")
        )
        or 0
    )
    if pending_apps:
        items.append(
            {
                "key": "pending_applications",
                "title": f"Заявки партнёров, ожидающие решения: {pending_apps}",
                "detail": "Проверьте заявки и одобрите подходящих партнёров.",
                "href": "/business/partners",
            }
        )
    if pending_conversions:
        items.append(
            {
                "key": "pending_conversions",
                "title": f"Конверсии ожидают подтверждения: {pending_conversions}",
                "detail": "Подтвердите или отклоните конверсии за выбранный период.",
                "href": "/business/conversions",
            }
        )
    converting_ids = set(
        (
            await db.execute(
                select(Conversion.offer_id)
                .where(Conversion.business_id == business_id, Conversion.created_at >= start)
                .group_by(Conversion.offer_id)
            )
        ).scalars()
    )
    quiet_query = select(Offer.id, Offer.name).where(
        Offer.business_id == business_id,
        Offer.status == "active",
    )
    if converting_ids:
        quiet_query = quiet_query.where(Offer.id.notin_(converting_ids))
    quiet_offers = (await db.execute(quiet_query.order_by(Offer.name.asc()).limit(2))).all()
    if quiet_offers and active_offers:
        names = ", ".join(name for _offer_id, name in quiet_offers)
        items.append(
            {
                "key": "quiet_offers",
                "title": "Офферы без конверсий за период",
                "detail": names,
                "href": "/business/offers",
            }
        )
    return items[:5]

