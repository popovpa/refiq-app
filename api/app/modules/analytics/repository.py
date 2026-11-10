from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.date_range import local_dates
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.analytics.metrics import money
from app.modules.analytics.scope import AnalyticsScope
from app.modules.campaigns.models import Campaign
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.partners.privacy import partner_public_display_name_from
from app.modules.sites.models import Site
from app.modules.users.models import User


@dataclass
class Totals:
    clicks: int
    conversions: int
    commission: Decimal | None
    currency: str | None
    commission_reason: str | None


@dataclass
class LabeledStat:
    entity_id: int | None
    label: str
    clicks: int
    conversions: int
    commission: Decimal | None
    currency: str | None
    commission_reason: str | None
    ownership: str


def _dialect(db: AsyncSession) -> str:
    bind = db.bind
    if bind is None:
        return "postgresql"
    return bind.dialect.name


def _bucket(column, timezone_name: str, granularity: str, dialect: str):
    if dialect == "sqlite":
        if granularity == "hour":
            return func.strftime("%Y-%m-%dT%H:00:00", column)
        return func.strftime("%Y-%m-%d", column)
    local = func.timezone(timezone_name, column)
    if granularity == "hour":
        return func.to_char(func.date_trunc("hour", local), 'YYYY-MM-DD"T"HH24:00:00')
    if granularity == "week":
        return func.to_char(func.date_trunc("week", local), "YYYY-MM-DD")
    return func.to_char(func.date_trunc("day", local), "YYYY-MM-DD")


def _rqcid(column, rqcids: list[str] | None):
    if rqcids is None:
        return None
    if not rqcids:
        return column == "__none__"
    return column.in_(rqcids)


def _click_filters(stmt, scope: AnalyticsScope, filt: AnalyticsFilters, start: datetime, end: datetime, exclusive: bool):
    stmt = (
        stmt.select_from(Click)
        .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
        .join(Offer, Offer.id == TrackingLink.offer_id)
    )
    if scope.role == "business":
        stmt = stmt.where(Offer.business_id == scope.business_id)
    else:
        stmt = stmt.where(TrackingLink.partner_id == scope.partner_id)
    stmt = stmt.where(Click.created_at >= start)
    stmt = stmt.where(Click.created_at < end if exclusive else Click.created_at <= end)
    if filt.offer_id is not None:
        stmt = stmt.where(TrackingLink.offer_id == filt.offer_id)
    if filt.campaign_id is not None:
        stmt = stmt.where(TrackingLink.campaign_id == filt.campaign_id)
    if filt.link_id is not None:
        stmt = stmt.where(TrackingLink.id == filt.link_id)
    if filt.partner_id is not None:
        stmt = stmt.where(TrackingLink.partner_id == filt.partner_id)
    if filt.traffic_source:
        stmt = stmt.where(TrackingLink.traffic_source == filt.traffic_source)
    clause = _rqcid(Click.rqcid, filt.rqcids)
    if clause is not None:
        stmt = stmt.where(clause)
    return stmt


def _conversion_filters(
    stmt,
    scope: AnalyticsScope,
    filt: AnalyticsFilters,
    start: datetime,
    end: datetime,
    statuses: tuple[str, ...],
    exclusive: bool,
    *,
    partner_only: bool = False,
):
    if scope.role == "business":
        stmt = stmt.where(Conversion.business_id == scope.business_id)
    else:
        stmt = stmt.where(Conversion.partner_id == scope.partner_id)
    if partner_only:
        stmt = stmt.where(Conversion.partner_id.is_not(None))
    stmt = stmt.where(Conversion.created_at >= start)
    stmt = stmt.where(Conversion.created_at < end if exclusive else Conversion.created_at <= end)
    if statuses:
        stmt = stmt.where(Conversion.status.in_(statuses))
    if filt.offer_id is not None:
        stmt = stmt.where(Conversion.offer_id == filt.offer_id)
    if filt.link_id is not None:
        stmt = stmt.where(Conversion.tracking_link_id == filt.link_id)
    if filt.partner_id is not None:
        stmt = stmt.where(Conversion.partner_id == filt.partner_id)
    clause = _rqcid(Conversion.click_id, filt.rqcids)
    if clause is not None:
        stmt = stmt.where(clause)
    if filt.campaign_id is not None or filt.traffic_source:
        stmt = stmt.join(TrackingLink, TrackingLink.id == Conversion.tracking_link_id)
        if filt.campaign_id is not None:
            stmt = stmt.where(TrackingLink.campaign_id == filt.campaign_id)
        if filt.traffic_source:
            stmt = stmt.where(TrackingLink.traffic_source == filt.traffic_source)
    return stmt


async def totals(
    db: AsyncSession,
    scope: AnalyticsScope,
    filt: AnalyticsFilters,
    *,
    start: datetime,
    end: datetime,
    exclusive: bool = False,
) -> Totals:
    clicks = int(
        await db.scalar(_click_filters(select(func.count(Click.id)), scope, filt, start, end, exclusive)) or 0
    )
    conversions = int(
        await db.scalar(
            _conversion_filters(
                select(func.count(Conversion.id)),
                scope,
                filt,
                start,
                end,
                filt.count_statuses,
                exclusive,
            )
        )
        or 0
    )
    commission, currency, reason = await _commission(db, scope, filt, start, end, exclusive)
    return Totals(clicks, conversions, commission, currency, reason)


async def _commission(db, scope, filt, start, end, exclusive: bool):
    rows = (
        await db.execute(
            _conversion_filters(
                select(
                    Conversion.currency,
                    func.coalesce(func.sum(Conversion.commission_amount), 0),
                ),
                scope,
                filt,
                start,
                end,
                filt.commission_statuses,
                exclusive,
                partner_only=True,
            ).group_by(Conversion.currency)
        )
    ).all()
    present = [(currency, money(amount)) for currency, amount in rows if money(amount) != 0 or currency]
    if not present:
        return Decimal("0.00"), None, None
    currencies = {currency or "RUB" for currency, amount in present if amount != 0}
    if len(currencies) > 1:
        return None, None, "mixed_currency"
    currency = next(iter(currencies), None) or (present[0][0] or "RUB")
    amount = sum((value for _currency, value in present), Decimal("0.00"))
    return money(amount), currency, None


async def status_counts(db, scope, filt, start, end) -> dict[str, int]:
    rows = (
        await db.execute(
            _conversion_filters(
                select(Conversion.status, func.count(Conversion.id)),
                scope,
                filt,
                start,
                end,
                (),
                False,
            ).group_by(Conversion.status)
        )
    ).all()
    return {status: int(count) for status, count in rows}


async def timeseries(db, scope, filt, granularity: str) -> list[dict]:
    date_range = filt.date_range
    dialect = _dialect(db)
    click_bucket = _bucket(Click.created_at, date_range.timezone, granularity, dialect)
    conv_bucket = _bucket(Conversion.created_at, date_range.timezone, granularity, dialect)
    click_rows = (
        await db.execute(
            _click_filters(
                select(click_bucket, func.count(Click.id)),
                scope,
                filt,
                date_range.start,
                date_range.end,
                False,
            ).group_by(click_bucket)
        )
    ).all()
    conv_rows = (
        await db.execute(
            _conversion_filters(
                select(conv_bucket, func.count(Conversion.id)),
                scope,
                filt,
                date_range.start,
                date_range.end,
                filt.count_statuses,
                False,
            ).group_by(conv_bucket)
        )
    ).all()
    clicks = {str(bucket): int(count) for bucket, count in click_rows if bucket}
    conversions = {str(bucket): int(count) for bucket, count in conv_rows if bucket}
    return _fill_buckets(date_range.start, date_range.end, date_range.timezone, granularity, clicks, conversions)


async def click_buckets(db, scope, filt, granularity: str) -> dict[str, int]:
    date_range = filt.date_range
    bucket = _bucket(Click.created_at, date_range.timezone, granularity, _dialect(db))
    rows = (
        await db.execute(
            _click_filters(
                select(bucket, func.count(Click.id)),
                scope,
                filt,
                date_range.start,
                date_range.end,
                False,
            ).group_by(bucket)
        )
    ).all()
    return {str(key): int(count) for key, count in rows if key}


async def click_sources(db, scope, filt) -> list[tuple[str | None, str | None, int]]:
    date_range = filt.date_range
    referer = case(
        (
            or_(TrackingLink.traffic_source.is_(None), TrackingLink.traffic_source == ""),
            Click.referer,
        ),
        else_="",
    )
    rows = (
        await db.execute(
            _click_filters(
                select(TrackingLink.traffic_source, referer, func.count(Click.id)),
                scope,
                filt,
                date_range.start,
                date_range.end,
                False,
            )
            .group_by(TrackingLink.traffic_source, referer)
            .order_by(func.count(Click.id).desc())
            .limit(501)
        )
    ).all()
    return [(source, ref, int(count)) for source, ref, count in rows]


def _source_column_query(stmt, filt: AnalyticsFilters):
    if filt.campaign_id is None and not filt.traffic_source:
        stmt = stmt.join(TrackingLink, TrackingLink.id == Conversion.tracking_link_id, isouter=True)
    return stmt


async def conversion_sources(db, scope, filt) -> list[tuple[str | None, int, Decimal | None, str | None, str | None]]:
    date_range = filt.date_range
    source = TrackingLink.traffic_source
    count_stmt = _source_column_query(
        _conversion_filters(
            select(source, func.count(Conversion.id)),
            scope,
            filt,
            date_range.start,
            date_range.end,
            filt.count_statuses,
            False,
        ),
        filt,
    )
    money_stmt = _source_column_query(
        _conversion_filters(
            select(
                source,
                Conversion.currency,
                func.coalesce(func.sum(Conversion.commission_amount), 0),
            ),
            scope,
            filt,
            date_range.start,
            date_range.end,
            filt.commission_statuses,
            False,
            partner_only=True,
        ),
        filt,
    )
    counts = {
        traffic_source: int(count)
        for traffic_source, count in (await db.execute(count_stmt.group_by(source))).all()
    }
    amounts: dict[str | None, dict[str, Decimal]] = {}
    for traffic_source, currency, amount in (await db.execute(money_stmt.group_by(source, Conversion.currency))).all():
        code = currency or "RUB"
        amounts.setdefault(traffic_source, {})
        amounts[traffic_source][code] = amounts[traffic_source].get(code, Decimal("0.00")) + money(amount)
    result = []
    for traffic_source in set(counts) | set(amounts):
        present = {code: value for code, value in amounts.get(traffic_source, {}).items() if value != 0}
        conversions = counts.get(traffic_source, 0)
        if len(present) > 1:
            result.append((traffic_source, conversions, None, None, "mixed_currency"))
        elif present:
            currency, amount = next(iter(present.items()))
            result.append((traffic_source, conversions, money(amount), currency, None))
        else:
            result.append((traffic_source, conversions, Decimal("0.00"), None, None))
    return result


async def top_offers(db, scope, filt) -> list[LabeledStat]:
    date_range = filt.date_range
    click_rows = (
        await db.execute(
            _click_filters(
                select(Offer.id, Offer.name, Offer.currency, func.count(Click.id)),
                scope,
                filt,
                date_range.start,
                date_range.end,
                False,
            ).group_by(Offer.id, Offer.name, Offer.currency)
        )
    ).all()
    conv_stmt = _conversion_filters(
        select(
            Offer.id,
            Offer.name,
            Offer.currency,
            Conversion.currency,
            func.count(Conversion.id),
            func.coalesce(func.sum(Conversion.commission_amount), 0),
        ).join(Offer, Offer.id == Conversion.offer_id),
        scope,
        filt,
        date_range.start,
        date_range.end,
        filt.commission_statuses,
        False,
        partner_only=True,
    )
    conv_rows = (await db.execute(conv_stmt.group_by(Offer.id, Offer.name, Offer.currency, Conversion.currency))).all()
    count_rows = (
        await db.execute(
            _conversion_filters(
                select(Conversion.offer_id, func.count(Conversion.id)).join(Offer, Offer.id == Conversion.offer_id),
                scope,
                filt,
                date_range.start,
                date_range.end,
                filt.count_statuses,
                False,
            ).group_by(Conversion.offer_id)
        )
    ).all()
    return _merge_offers(click_rows, conv_rows, count_rows)


async def efficiency(db, scope, filt) -> list[LabeledStat]:
    date_range = filt.date_range
    if scope.role == "partner":
        return await _link_efficiency(db, scope, filt, date_range.start, date_range.end)
    return await _partner_efficiency(db, scope, filt, date_range.start, date_range.end)


async def _partner_efficiency(db, scope, filt, start, end) -> list[LabeledStat]:
    click_rows = (
        await db.execute(
            _click_filters(
                select(TrackingLink.partner_id, func.count(Click.id)),
                scope,
                filt,
                start,
                end,
                False,
            ).group_by(TrackingLink.partner_id)
        )
    ).all()
    conv_rows = (
        await db.execute(
            _conversion_filters(
                select(Conversion.partner_id, func.count(Conversion.id)),
                scope,
                filt,
                start,
                end,
                filt.count_statuses,
                False,
            ).group_by(Conversion.partner_id)
        )
    ).all()
    money_rows = (
        await db.execute(
            _conversion_filters(
                select(
                    Conversion.partner_id,
                    Conversion.currency,
                    func.coalesce(func.sum(Conversion.commission_amount), 0),
                ),
                scope,
                filt,
                start,
                end,
                filt.commission_statuses,
                False,
                partner_only=True,
            ).group_by(Conversion.partner_id, Conversion.currency)
        )
    ).all()
    ids = [partner_id for partner_id, _count in click_rows if partner_id] + [
        partner_id for partner_id, _count in conv_rows if partner_id
    ]
    names = await _partner_names(db, ids)
    clicks = {partner_id: int(count) for partner_id, count in click_rows}
    conversions = {partner_id: int(count) for partner_id, count in conv_rows}
    commissions = _money_by_entity(money_rows)
    keys = set(clicks) | set(conversions)
    rows = []
    for key in keys:
        amount, currency, reason = commissions.get(key, (Decimal("0.00"), None, None))
        if key is None:
            label, ownership, amount, currency, reason = (
                "Собственное продвижение",
                "business",
                Decimal("0.00"),
                currency,
                None,
            )
        else:
            label, ownership = names.get(key, f"Партнёр #{key}"), "partner"
        rows.append(
            LabeledStat(key, label, clicks.get(key, 0), conversions.get(key, 0), amount, currency, reason, ownership)
        )
    rows.sort(key=lambda item: item.clicks, reverse=True)
    return rows[:8]


async def _link_efficiency(db, scope, filt, start, end) -> list[LabeledStat]:
    click_rows = (
        await db.execute(
            _click_filters(
                select(TrackingLink.id, TrackingLink.name, func.count(Click.id)),
                scope,
                filt,
                start,
                end,
                False,
            ).group_by(TrackingLink.id, TrackingLink.name)
        )
    ).all()
    conv_rows = (
        await db.execute(
            _conversion_filters(
                select(Conversion.tracking_link_id, func.count(Conversion.id)),
                scope,
                filt,
                start,
                end,
                filt.count_statuses,
                False,
            ).group_by(Conversion.tracking_link_id)
        )
    ).all()
    money_rows = (
        await db.execute(
            _conversion_filters(
                select(
                    Conversion.tracking_link_id,
                    Conversion.currency,
                    func.coalesce(func.sum(Conversion.commission_amount), 0),
                ),
                scope,
                filt,
                start,
                end,
                filt.commission_statuses,
                False,
                partner_only=True,
            ).group_by(Conversion.tracking_link_id, Conversion.currency)
        )
    ).all()
    names = {link_id: name or f"Ссылка #{link_id}" for link_id, name, _count in click_rows}
    clicks = {link_id: int(count) for link_id, _name, count in click_rows}
    conversions = {link_id: int(count) for link_id, count in conv_rows if link_id}
    commissions = _money_by_entity(money_rows)
    rows = []
    for link_id in set(clicks) | set(conversions):
        amount, currency, reason = commissions.get(link_id, (Decimal("0.00"), None, None))
        rows.append(
            LabeledStat(
                link_id,
                names.get(link_id, f"Ссылка #{link_id}"),
                clicks.get(link_id, 0),
                conversions.get(link_id, 0),
                amount,
                currency,
                reason,
                "partner",
            )
        )
    rows.sort(key=lambda item: item.clicks, reverse=True)
    return rows[:8]


async def comparison_base(db, scope, filt) -> list[LabeledStat]:
    return await efficiency(db, scope, filt)


async def filter_options(db: AsyncSession, scope: AnalyticsScope) -> dict:
    if scope.role == "business":
        offers = (
            await db.execute(
                select(Offer.id, Offer.name)
                .where(Offer.business_id == scope.business_id)
                .order_by(Offer.name)
                .limit(200)
            )
        ).all()
        campaigns = (
            await db.execute(
                select(Campaign.id, Campaign.name)
                .join(Offer, Offer.id == Campaign.offer_id)
                .where(Offer.business_id == scope.business_id)
                .order_by(Campaign.name)
                .limit(200)
            )
        ).all()
        sites = (
            await db.execute(
                select(Site.id, Site.name).where(Site.business_id == scope.business_id).order_by(Site.name).limit(200)
            )
        ).all()
        sources = (
            await db.execute(
                select(TrackingLink.traffic_source)
                .join(Offer, Offer.id == TrackingLink.offer_id)
                .where(Offer.business_id == scope.business_id, TrackingLink.traffic_source.is_not(None))
                .distinct()
            )
        ).scalars()
        partner_ids = (
            await db.execute(
                select(TrackingLink.partner_id)
                .join(Offer, Offer.id == TrackingLink.offer_id)
                .where(Offer.business_id == scope.business_id, TrackingLink.partner_id.is_not(None))
                .distinct()
                .limit(200)
            )
        ).scalars()
        names = await _partner_names(db, list(partner_ids))
        partners = [{"id": partner_id, "name": name} for partner_id, name in names.items()]
        links: list[dict] = []
        site_rows = [{"id": site_id, "name": name} for site_id, name in sites]
    else:
        offers = (
            await db.execute(
                select(Offer.id, Offer.name)
                .join(TrackingLink, TrackingLink.offer_id == Offer.id)
                .where(TrackingLink.partner_id == scope.partner_id)
                .distinct()
                .order_by(Offer.name)
                .limit(200)
            )
        ).all()
        campaigns = (
            await db.execute(
                select(Campaign.id, Campaign.name)
                .where(Campaign.partner_id == scope.partner_id)
                .order_by(Campaign.name)
                .limit(200)
            )
        ).all()
        link_rows = (
            await db.execute(
                select(TrackingLink.id, TrackingLink.name)
                .where(TrackingLink.partner_id == scope.partner_id)
                .order_by(TrackingLink.created_at.desc())
                .limit(200)
            )
        ).all()
        sources = (
            await db.execute(
                select(TrackingLink.traffic_source)
                .where(TrackingLink.partner_id == scope.partner_id, TrackingLink.traffic_source.is_not(None))
                .distinct()
            )
        ).scalars()
        partners = []
        links = [{"id": link_id, "name": name or f"Ссылка #{link_id}"} for link_id, name in link_rows]
        site_rows = []
    return {
        "offers": [{"id": offer_id, "name": name} for offer_id, name in offers],
        "campaigns": [{"id": campaign_id, "name": name} for campaign_id, name in campaigns],
        "links": links,
        "partners": partners,
        "sites": site_rows,
        "traffic_sources": sorted({item for item in sources if item}),
    }


def _merge_offers(click_rows, conv_rows, count_rows) -> list[LabeledStat]:
    stats: dict[int, LabeledStat] = {}
    for offer_id, name, currency, count in click_rows:
        stats[int(offer_id)] = LabeledStat(
            int(offer_id), name, int(count), 0, Decimal("0.00"), currency, None, "offer"
        )
    conversions = {int(offer_id): int(count) for offer_id, count in count_rows}
    money_map: dict[int, dict[str, Decimal]] = {}
    for offer_id, name, offer_currency, conv_currency, _count, amount in conv_rows:
        stat = stats.get(int(offer_id))
        if stat is None:
            stat = LabeledStat(int(offer_id), name, 0, 0, Decimal("0.00"), offer_currency, None, "offer")
            stats[int(offer_id)] = stat
        code = conv_currency or offer_currency or "RUB"
        money_map.setdefault(int(offer_id), {})
        money_map[int(offer_id)][code] = money_map[int(offer_id)].get(code, Decimal("0.00")) + money(amount)
    for offer_id, stat in stats.items():
        stat.conversions = conversions.get(offer_id, 0)
        amounts = {code: value for code, value in money_map.get(offer_id, {}).items() if value != 0}
        if len(amounts) > 1:
            stat.commission = None
            stat.currency = None
            stat.commission_reason = "mixed_currency"
        elif amounts:
            stat.currency, stat.commission = next(iter(amounts.items()))
            stat.commission = money(stat.commission)
        else:
            stat.commission = Decimal("0.00")
    rows = list(stats.values())
    rows.sort(key=lambda item: (item.clicks, item.conversions), reverse=True)
    return rows[:8]


def _money_by_entity(rows) -> dict:
    grouped: dict = {}
    for entity_id, currency, amount in rows:
        grouped.setdefault(entity_id, {})
        code = currency or "RUB"
        grouped[entity_id][code] = grouped[entity_id].get(code, Decimal("0.00")) + money(amount)
    result = {}
    for entity_id, amounts in grouped.items():
        present = {code: value for code, value in amounts.items() if value != 0}
        if len(present) > 1:
            result[entity_id] = (None, None, "mixed_currency")
        elif present:
            currency, amount = next(iter(present.items()))
            result[entity_id] = (money(amount), currency, None)
        else:
            result[entity_id] = (Decimal("0.00"), None, None)
    return result


async def _partner_names(db: AsyncSession, partner_ids: list[int]) -> dict[int, str]:
    unique = sorted({int(item) for item in partner_ids if item})
    if not unique:
        return {}
    rows = (
        await db.execute(
            select(PartnerProfile, User)
            .join(User, User.id == PartnerProfile.user_id)
            .where(PartnerProfile.id.in_(unique))
        )
    ).all()
    return {profile.id: partner_public_display_name_from(profile, user) for profile, user in rows}


def _fill_buckets(start, end, timezone_name, granularity, clicks: dict[str, int], conversions: dict[str, int]):
    if granularity != "day":
        keys = sorted(set(clicks) | set(conversions))
    else:
        keys = [day.isoformat() for day in local_dates(start, end, timezone_name)]
    if len(keys) > 120:
        keys = keys[:120]
    return [
        {"bucket": key, "clicks": clicks.get(key, 0), "conversions": conversions.get(key, 0)}
        for key in keys
    ]


async def click_rqcids(db, scope, filt, start: datetime, end: datetime) -> list[str] | None:
    from app.modules.analytics.metrics import MAX_RQCID_INTERSECTION

    rows = (
        await db.execute(
            _click_filters(select(Click.rqcid), scope, filt, start, end, False).limit(MAX_RQCID_INTERSECTION + 1)
        )
    ).scalars().all()
    if len(rows) > MAX_RQCID_INTERSECTION:
        return None
    return [item for item in rows if item]


def granularity_for(start: datetime, end: datetime) -> str:
    span = end - start
    if span.total_seconds() <= 2 * 86400:
        return "hour"
    if span.days <= 92:
        return "day"
    return "week"
