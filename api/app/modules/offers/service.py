from app.common.date_range import ResolvedDateRange, local_dates, local_day_key

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer, OfferCommissionRule, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile
from app.modules.products.models import Product
from app.modules.users.models import User

ATTRIBUTION_MODEL = "last eligible partner click within attribution window"


def commission_payload(rules: list[OfferCommissionRule]) -> list[dict]:
    return [
        {
            "id": rule.id,
            "type": rule.type,
            "value": float(rule.value),
            "currency": rule.currency,
        }
        for rule in rules
    ]


def offer_public_fields(offer: Offer) -> dict:
    return {
        "id": offer.id,
        "name": offer.name,
        "description": offer.description,
        "image_url": offer.image_url,
        "category": offer.category,
        "geo": offer.geo,
        "status": offer.status,
        "visibility": offer.visibility,
        "access_policy": offer.access_policy,
        "conversion_type": offer.conversion_type,
        "attribution_window_days": offer.attribution_window_days,
        "attribution_model": ATTRIBUTION_MODEL,
        "currency": offer.currency,
        "allowed_traffic": offer.allowed_traffic or [],
        "forbidden_traffic": offer.forbidden_traffic or [],
        "partner_notes": offer.partner_notes,
        "materials": offer.materials or [],
        "commission_rules": commission_payload(offer.commission_rules),
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
    }


def cr(clicks: int, conversions: int) -> float:
    if clicks <= 0:
        return 0.0
    return round(conversions / clicks * 100, 2)


def epc(clicks: int, earnings: float) -> float:
    if clicks <= 0:
        return 0.0
    return round(earnings / clicks, 2)


async def offer_stats(
    db: AsyncSession,
    offer_id: int,
    partner_id: int | None = None,
    date_range: ResolvedDateRange | None = None,
) -> dict:
    click_q = (
        select(func.count(Click.id))
        .select_from(Click)
        .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
        .where(TrackingLink.offer_id == offer_id)
    )
    conv_q = select(func.count(Conversion.id)).where(Conversion.offer_id == offer_id)
    revenue_q = select(func.coalesce(func.sum(Conversion.amount), 0)).where(
        Conversion.offer_id == offer_id,
        Conversion.status.in_(["approved", "paid"]),
    )
    commission_q = select(func.coalesce(func.sum(Commission.amount), 0)).where(
        Commission.conversion_id.in_(select(Conversion.id).where(Conversion.offer_id == offer_id))
    )
    if partner_id is not None:
        click_q = click_q.where(TrackingLink.partner_id == partner_id)
        conv_q = conv_q.where(Conversion.partner_id == partner_id)
        revenue_q = revenue_q.where(Conversion.partner_id == partner_id)
        commission_q = select(func.coalesce(func.sum(Commission.amount), 0)).where(
            Commission.partner_id == partner_id,
            Commission.conversion_id.in_(
                select(Conversion.id).where(Conversion.offer_id == offer_id, Conversion.partner_id == partner_id)
            ),
        )
    if date_range is not None:
        click_q = click_q.where(Click.created_at >= date_range.start, Click.created_at <= date_range.end)
        conv_q = conv_q.where(Conversion.created_at >= date_range.start, Conversion.created_at <= date_range.end)
        revenue_q = revenue_q.where(
            Conversion.created_at >= date_range.start,
            Conversion.created_at <= date_range.end,
        )
        commission_q = commission_q.where(
            Commission.created_at >= date_range.start,
            Commission.created_at <= date_range.end,
        )

    clicks = int(await db.scalar(click_q) or 0)
    conversions = int(await db.scalar(conv_q) or 0)
    revenue = float(await db.scalar(revenue_q) or 0)
    commissions = float(await db.scalar(commission_q) or 0)
    return {
        "clicks": clicks,
        "conversions": conversions,
        "cr": cr(clicks, conversions),
        "revenue": revenue,
        "commissions": commissions,
        "epc": epc(clicks, commissions),
    }


async def offer_source_stats(
    db: AsyncSession,
    offer_id: int,
    *,
    business_owned: bool,
    date_range: ResolvedDateRange | None = None,
) -> dict:
    owner_filter = TrackingLink.business_id.is_not(None) if business_owned else TrackingLink.partner_id.is_not(None)
    click_q = (
        select(func.count(Click.id))
        .select_from(Click)
        .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
        .where(TrackingLink.offer_id == offer_id, owner_filter)
    )
    conv_q = (
        select(func.count(Conversion.id))
        .join(TrackingLink, Conversion.tracking_link_id == TrackingLink.id)
        .where(Conversion.offer_id == offer_id, owner_filter)
    )
    revenue_q = (
        select(func.coalesce(func.sum(Conversion.amount), 0))
        .join(TrackingLink, Conversion.tracking_link_id == TrackingLink.id)
        .where(
            Conversion.offer_id == offer_id,
            Conversion.status.in_(["approved", "paid"]),
            owner_filter,
        )
    )
    commission_q = (
        select(func.coalesce(func.sum(Commission.amount), 0))
        .select_from(Commission)
        .join(Conversion, Commission.conversion_id == Conversion.id)
        .join(TrackingLink, Conversion.tracking_link_id == TrackingLink.id)
        .where(Conversion.offer_id == offer_id, owner_filter)
    )
    if date_range is not None:
        click_q = click_q.where(Click.created_at >= date_range.start, Click.created_at <= date_range.end)
        conv_q = conv_q.where(Conversion.created_at >= date_range.start, Conversion.created_at <= date_range.end)
        revenue_q = revenue_q.where(
            Conversion.created_at >= date_range.start,
            Conversion.created_at <= date_range.end,
        )
        commission_q = commission_q.where(
            Commission.created_at >= date_range.start,
            Commission.created_at <= date_range.end,
        )
    clicks = int(await db.scalar(click_q) or 0)
    conversions = int(await db.scalar(conv_q) or 0)
    revenue = float(await db.scalar(revenue_q) or 0)
    commissions = float(await db.scalar(commission_q) or 0)
    return {
        "clicks": clicks,
        "conversions": conversions,
        "cr": cr(clicks, conversions),
        "revenue": revenue,
        "commissions": commissions,
    }


async def offer_link_stats(
    db: AsyncSession,
    offer_id: int,
    date_range: ResolvedDateRange | None = None,
) -> dict[int, dict[str, int]]:
    click_q = (
        select(Click.tracking_link_id, func.count(Click.id))
        .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
        .where(TrackingLink.offer_id == offer_id)
        .group_by(Click.tracking_link_id)
    )
    conv_q = (
        select(Conversion.tracking_link_id, func.count(Conversion.id))
        .where(Conversion.offer_id == offer_id, Conversion.tracking_link_id.is_not(None))
        .group_by(Conversion.tracking_link_id)
    )
    if date_range is not None:
        click_q = click_q.where(Click.created_at >= date_range.start, Click.created_at <= date_range.end)
        conv_q = conv_q.where(
            Conversion.created_at >= date_range.start,
            Conversion.created_at <= date_range.end,
        )
    click_rows = (await db.execute(click_q)).all()
    conv_rows = (await db.execute(conv_q)).all()
    clicks = {int(row[0]): int(row[1]) for row in click_rows}
    conversions = {int(row[0]): int(row[1]) for row in conv_rows}
    return {
        link_id: {
            "clicks": clicks.get(link_id, 0),
            "conversions": conversions.get(link_id, 0),
        }
        for link_id in set(clicks) | set(conversions)
    }


async def offer_timeseries(
    db: AsyncSession,
    offer_id: int,
    days: int = 14,
    date_range: ResolvedDateRange | None = None,
) -> list[dict]:
    if date_range is None:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        date_range = ResolvedDateRange(start, now, "UTC")
    start, end = date_range.start, date_range.end
    click_rows = (
        await db.execute(
            select(Click.created_at)
            .select_from(Click)
            .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
            .where(
                TrackingLink.offer_id == offer_id,
                Click.created_at >= start,
                Click.created_at <= end,
            )
        )
    ).all()
    conv_rows = (
        await db.execute(
            select(Conversion.created_at).where(
                Conversion.offer_id == offer_id,
                Conversion.created_at >= start,
                Conversion.created_at <= end,
            )
        )
    ).all()
    clicks_map: dict[str, int] = {}
    conv_map: dict[str, int] = {}
    for (created_at,) in click_rows:
        key = local_day_key(created_at, date_range.timezone)
        clicks_map[key] = clicks_map.get(key, 0) + 1
    for (created_at,) in conv_rows:
        key = local_day_key(created_at, date_range.timezone)
        conv_map[key] = conv_map.get(key, 0) + 1
    series = []
    for day in local_dates(start, end, date_range.timezone):
        key = day.isoformat()
        series.append(
            {
                "date": key,
                "clicks": clicks_map.get(key, 0),
                "conversions": conv_map.get(key, 0),
            }
        )
    return series


async def apply_commission_update(
    db: AsyncSession,
    offer: Offer,
    commission_type: str | None,
    commission_value: float | None,
    commission_currency: str | None,
) -> None:
    if commission_type is None and commission_value is None and commission_currency is None:
        return
    rule = offer.commission_rules[0] if offer.commission_rules else None
    if rule is None:
        rule = OfferCommissionRule(
            offer_id=offer.id,
            type=commission_type or "percent",
            value=commission_value if commission_value is not None else 0,
            currency=commission_currency or offer.currency,
        )
        db.add(rule)
        return
    if commission_type is not None:
        rule.type = commission_type
    if commission_value is not None:
        rule.value = commission_value
    if commission_currency is not None:
        rule.currency = commission_currency
        offer.currency = commission_currency


async def ensure_business_partner(db: AsyncSession, business_id: int, partner_id: int, status: str) -> None:
    from app.modules.partners.models import BusinessPartner

    existing = (
        await db.execute(
            select(BusinessPartner).where(
                BusinessPartner.business_id == business_id,
                BusinessPartner.partner_id == partner_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if status == "active" and existing.status != "active":
            existing.status = "active"
        return
    db.add(
        BusinessPartner(
            business_id=business_id,
            partner_id=partner_id,
            status=status,
        )
    )


async def product_url_for_offer(db: AsyncSession, offer: Offer) -> str | None:
    if not offer.product_id:
        return None
    product = (
        await db.execute(select(Product).where(Product.id == offer.product_id))
    ).scalar_one_or_none()
    return product.url if product else None


def partner_access_query() -> Select:
    return (
        select(OfferPartnerAccess, PartnerProfile, User)
        .join(PartnerProfile, OfferPartnerAccess.partner_id == PartnerProfile.id)
        .join(User, PartnerProfile.user_id == User.id)
    )
