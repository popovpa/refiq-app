from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CampaignStatus, OfferStatus
from app.core.exceptions import AppError
from app.core.ids import parse_id
from app.modules.campaigns.models import Campaign
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink, TrackingLinkStatus
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.offers.service import cr
from app.modules.partners.models import PartnerProfile
from app.modules.users.models import UserRole


def period_start(days: int) -> datetime:
    start = datetime.now(timezone.utc) - timedelta(days=days - 1)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def build_link_filters(
    *,
    partner_id: int,
    q: str | None = None,
    offer_id: int | None = None,
    traffic_source: str | None = None,
    status: str | None = None,
):
    filters = [TrackingLink.partner_id == partner_id]
    if offer_id is not None:
        filters.append(TrackingLink.offer_id == offer_id)
    if traffic_source:
        filters.append(TrackingLink.traffic_source == traffic_source)
    if status:
        filters.append(TrackingLink.status == status)
    if q:
        needle = f"%{q.strip()}%"
        filters.append(
            or_(
                TrackingLink.name.ilike(needle),
                TrackingLink.short_code.ilike(needle),
                Offer.name.ilike(needle),
            )
        )
    return filters


async def batch_link_stats(
    db: AsyncSession,
    link_ids: list[int],
    partner_id: int,
    days: int,
) -> dict[int, dict]:
    if not link_ids:
        return {}

    start = period_start(days)

    all_time_clicks_rows = (
        await db.execute(
            select(Click.tracking_link_id, func.count(Click.id))
            .where(Click.tracking_link_id.in_(link_ids))
            .group_by(Click.tracking_link_id)
        )
    ).all()
    all_time_clicks = {row[0]: int(row[1]) for row in all_time_clicks_rows}

    all_time_conv_rows = (
        await db.execute(
            select(Conversion.tracking_link_id, func.count(Conversion.id))
            .where(
                Conversion.tracking_link_id.in_(link_ids),
                Conversion.partner_id == partner_id,
            )
            .group_by(Conversion.tracking_link_id)
        )
    ).all()
    all_time_conversions = {row[0]: int(row[1]) for row in all_time_conv_rows}

    period_click_rows = (
        await db.execute(
            select(Click.tracking_link_id, func.count(Click.id))
            .where(
                Click.tracking_link_id.in_(link_ids),
                Click.created_at >= start,
            )
            .group_by(Click.tracking_link_id)
        )
    ).all()
    period_clicks = {row[0]: int(row[1]) for row in period_click_rows}

    period_conv_rows = (
        await db.execute(
            select(Conversion.tracking_link_id, func.count(Conversion.id))
            .where(
                Conversion.tracking_link_id.in_(link_ids),
                Conversion.partner_id == partner_id,
                Conversion.created_at >= start,
            )
            .group_by(Conversion.tracking_link_id)
        )
    ).all()
    period_conversions = {row[0]: int(row[1]) for row in period_conv_rows}

    period_earned_rows = (
        await db.execute(
            select(
                Conversion.tracking_link_id,
                func.coalesce(func.sum(Commission.amount), 0),
            )
            .join(Commission, Commission.conversion_id == Conversion.id)
            .where(
                Conversion.tracking_link_id.in_(link_ids),
                Conversion.partner_id == partner_id,
                Commission.created_at >= start,
            )
            .group_by(Conversion.tracking_link_id)
        )
    ).all()
    period_earned = {row[0]: float(row[1]) for row in period_earned_rows}

    stats: dict[int, dict] = {}
    for link_id in link_ids:
        has_data = all_time_clicks.get(link_id, 0) > 0 or all_time_conversions.get(link_id, 0) > 0
        clicks = period_clicks.get(link_id, 0)
        conversions = period_conversions.get(link_id, 0)
        earned = period_earned.get(link_id, 0.0)
        stats[link_id] = {
            "has_stat_data": has_data,
            "clicks": clicks if has_data else None,
            "conversions": conversions if has_data else None,
            "cr": cr(clicks, conversions) if has_data else None,
            "earned": earned if has_data else None,
        }
    return stats


async def link_filter_options(db: AsyncSession, partner_id: int) -> dict:
    rows = (
        await db.execute(
            select(
                TrackingLink.offer_id,
                Offer.name.label("offer_name"),
                TrackingLink.traffic_source,
            )
            .join(Offer, TrackingLink.offer_id == Offer.id)
            .where(TrackingLink.partner_id == partner_id)
            .order_by(Offer.name.asc())
        )
    ).all()

    offers: dict[int, str] = {}
    sources: set[str] = set()
    for row in rows:
        offers[row.offer_id] = row.offer_name
        if row.traffic_source:
            sources.add(row.traffic_source)

    return {
        "offers": [{"id": offer_id, "name": name} for offer_id, name in offers.items()],
        "traffic_sources": sorted(sources),
    }


async def links_summary(
    db: AsyncSession,
    *,
    partner_id: int,
    days: int,
    filters,
) -> dict:
    base = (
        select(TrackingLink.id, TrackingLink.status)
        .join(Offer, TrackingLink.offer_id == Offer.id)
        .where(*filters)
    )
    rows = (await db.execute(base)).all()
    link_ids = [row.id for row in rows]
    active_links = sum(1 for row in rows if row.status == "ACTIVE")

    if not link_ids:
        return {
            "active_links": 0,
            "clicks": 0,
            "conversions": 0,
            "earned": 0.0,
        }

    stats = await batch_link_stats(db, link_ids, partner_id, days)
    clicks = sum(item["clicks"] or 0 for item in stats.values())
    conversions = sum(item["conversions"] or 0 for item in stats.values())
    earned = sum(item["earned"] or 0.0 for item in stats.values())

    return {
        "active_links": active_links,
        "clicks": clicks,
        "conversions": conversions,
        "earned": round(earned, 2),
    }


async def assert_can_activate_link(
    db: AsyncSession,
    *,
    link: TrackingLink,
    profile: PartnerProfile,
    user_id: str,
) -> None:
    if profile.status != "active":
        raise AppError("PARTNER_INACTIVE", "Не удалось активировать ссылку.", 403)

    role = (
        await db.execute(
            select(UserRole).where(
                UserRole.user_id == parse_id(user_id),
                UserRole.role == "partner",
                UserRole.status == "active",
            )
        )
    ).scalar_one_or_none()
    if not role:
        raise AppError("PARTNER_INACTIVE", "Не удалось активировать ссылку.", 403)

    offer = (await db.execute(select(Offer).where(Offer.id == link.offer_id))).scalar_one_or_none()
    if not offer:
        raise AppError("OFFER_UNAVAILABLE", "Оффер больше недоступен для продвижения.", 403)

    if offer.status == OfferStatus.PAUSED.value:
        raise AppError(
            "OFFER_PAUSED",
            "Оффер временно приостановлен. Ссылка может быть активирована после возобновления оффера.",
            403,
        )
    if offer.status != OfferStatus.ACTIVE.value:
        raise AppError("OFFER_UNAVAILABLE", "Оффер больше недоступен для продвижения.", 403)

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
        raise AppError("OFFER_UNAVAILABLE", "Оффер больше недоступен для продвижения.", 403)

    if link.campaign_id is not None:
        campaign = (
            await db.execute(
                select(Campaign).where(
                    Campaign.id == link.campaign_id,
                    Campaign.partner_id == profile.id,
                    Campaign.offer_id == link.offer_id,
                )
            )
        ).scalar_one_or_none()
        if not campaign or campaign.status != CampaignStatus.ACTIVE.value:
            raise AppError("LINK_UNAVAILABLE", "Ссылка больше не может быть использована.", 403)
