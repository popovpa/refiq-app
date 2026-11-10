from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics import repository as repo
from app.modules.analytics.chsql import (
    behavior_sql,
    comparison_sql,
    depth_sql,
    funnel_sql,
    pages_sql,
    paths_sql,
    performance_series_sql,
    performance_sql,
    quality_series_sql,
    rqcid_sql_query,
    scope_clause,
    session_sql,
    slow_pages_sql,
)
from app.modules.analytics.clickhouse import ClickHouseUnavailable, get_clickhouse
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.analytics.metrics import (
    DEFINITIONS,
    MAX_RQCID_INTERSECTION,
    as_text,
    change_pct,
    coverage_quality,
    decimal_or_none,
    epc,
    money,
    postgres_click_policy,
    ratio,
)
from app.modules.analytics.repository import LabeledStat
from app.modules.analytics.schemas import (
    BehaviorResponse,
    Efficiency,
    EntityRow,
    FilterOption,
    FiltersResponse,
    FunnelLoss,
    FunnelResponse,
    FunnelStep,
    Meta,
    Metric,
    OverviewResponse,
    PageRow,
    PathEdge,
    PerformanceResponse,
    QualityResponse,
    ScrollPoint,
    SeriesPoint,
    SlowPage,
    SourceRow,
    SourcesResponse,
    StatusSlice,
    TrafficOption,
)
from app.modules.analytics.scope import AnalyticsScope, authorize_filters, resolve_scope
from app.modules.analytics.sources import catalog_label, classify_source, normalize_page

logger = structlog.get_logger()

EFFICIENCY_FORMULA = "CR = конверсии / клики × 100. Длина полосы сравнивает CR с максимумом в этом списке."
ROI_REASON = "media_spend_not_collected"


async def prepare(db: AsyncSession, session_data: dict, filt: AnalyticsFilters) -> AnalyticsScope:
    scope = await resolve_scope(db, session_data)
    await authorize_filters(db, scope, filt)
    return scope


def _meta(scope: AnalyticsScope, filt: AnalyticsFilters, clickhouse: str) -> Meta:
    return Meta(
        role=scope.role,
        period_from=filt.date_range.start,
        to=filt.date_range.end,
        timezone=filt.date_range.timezone,
        clickhouse=clickhouse,
        definitions=DEFINITIONS,
    )


def _count(value: int | None, previous: int | None = None, quality: str = "reliable", reason: str | None = None) -> Metric:
    return Metric(
        value=None if value is None else str(value),
        change_pct=as_text(change_pct(value, previous)),
        quality=quality,
        reason=reason,
        unit="count",
    )


def _rate(
    value: Decimal | None,
    previous: Decimal | None = None,
    *,
    quality: str = "reliable",
    reason: str | None = None,
    unit: str = "percent",
    currency: str | None = None,
    samples: int | None = None,
    coverage: Decimal | None = None,
) -> Metric:
    return Metric(
        value=as_text(value),
        change_pct=as_text(change_pct(value, previous)),
        quality=quality,
        reason=reason,
        unit=unit,
        currency=currency,
        samples=samples,
        coverage=as_text(coverage) if coverage is not None else None,
    )


def _missing(reason: str, unit: str = "count") -> Metric:
    return Metric(value=None, quality="unavailable", reason=reason, unit=unit)


def _where(scope: AnalyticsScope, filt: AnalyticsFilters, start=None, end=None):
    return scope_clause(
        role=scope.role,
        business_id=scope.business_id,
        partner_id=scope.partner_id,
        filt=filt,
        start=start or filt.date_range.start,
        end=end or filt.date_range.end,
    )


async def _ch(sql: str, params: dict) -> tuple[bool, list[dict]]:
    try:
        return True, await get_clickhouse().query(sql, params)
    except ClickHouseUnavailable:
        logger.warning("analytics_clickhouse_unavailable")
        return False, []


def _first(rows: list[dict]) -> dict:
    return rows[0] if rows else {}


def _whole(value) -> int:
    parsed = _float(value)
    if parsed is None:
        return 0
    return int(parsed)


def _float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


async def _constrain(scope: AnalyticsScope, filt: AnalyticsFilters, start, end) -> str:
    if not filt.needs_intersection:
        return "unused"
    probe = replace(filt, rqcids=None)
    where, params = _where(scope, probe, start, end)
    ok, rows = await _ch(rqcid_sql_query(where), params)
    if not ok:
        filt.postgres_blocked_reason = "clickhouse_unavailable"
        return "unavailable"
    ids = [str(row.get("rqcid")) for row in rows if row.get("rqcid")]
    truncated = len(ids) > MAX_RQCID_INTERSECTION
    policy = postgres_click_policy(
        needs_intersection=True,
        clickhouse_ok=True,
        rqcid_count=None if truncated else len(ids),
        truncated=truncated,
    )
    if policy == "subset":
        filt.rqcids = ids[:MAX_RQCID_INTERSECTION]
        return "ok"
    if policy == "none":
        filt.rqcids = []
        return "ok"
    filt.postgres_blocked_reason = "filter_too_broad"
    return "ok"


async def _previous_totals(db, scope, filt: AnalyticsFilters):
    if filt.postgres_blocked_reason:
        return None
    window = filt.date_range
    previous = replace(filt, rqcids=None, postgres_blocked_reason=None)
    state = await _constrain(scope, previous, window.previous_start, window.previous_end)
    if previous.postgres_blocked_reason or state == "unavailable":
        return None
    return await repo.totals(
        db,
        scope,
        previous,
        start=window.previous_start,
        end=window.previous_end,
        exclusive=True,
    )


def _kpis_from_totals(current, previous, blocked: str | None) -> dict[str, Metric]:
    if blocked or current is None:
        reason = blocked or "unavailable"
        return {key: _missing(reason, unit) for key, unit in (
            ("clicks", "count"),
            ("conversions", "count"),
            ("cr", "percent"),
            ("commission", "money"),
            ("epc", "money"),
        )}
    prev_clicks = previous.clicks if previous else None
    prev_conversions = previous.conversions if previous else None
    prev_commission = previous.commission if previous else None
    cr = ratio(current.conversions, current.clicks)
    prev_cr = ratio(prev_conversions, prev_clicks) if previous else None
    current_epc = epc(current.commission, current.clicks)
    prev_epc = epc(prev_commission, prev_clicks) if previous else None
    return {
        "clicks": _count(current.clicks, prev_clicks),
        "conversions": _count(current.conversions, prev_conversions),
        "cr": _rate(cr, prev_cr),
        "commission": _rate(
            current.commission,
            prev_commission,
            quality="unavailable" if current.commission_reason else "reliable",
            reason=current.commission_reason,
            unit="money",
            currency=current.currency,
        ),
        "epc": _rate(
            current_epc,
            prev_epc,
            quality="unavailable" if current.commission_reason else "reliable",
            reason=current.commission_reason,
            unit="money",
            currency=current.currency,
        ),
    }


def _series(rows: list[dict]) -> list[SeriesPoint]:
    return [
        SeriesPoint(
            bucket=row["bucket"],
            clicks=row["clicks"],
            conversions=row["conversions"],
            cr=as_text(ratio(row["conversions"], row["clicks"])),
        )
        for row in rows
    ]


def _entity(stat: LabeledStat, href: str | None = None) -> EntityRow:
    return EntityRow(
        id=None if stat.entity_id is None else str(stat.entity_id),
        label=stat.label,
        href=href,
        clicks=stat.clicks,
        conversions=stat.conversions,
        cr=as_text(ratio(stat.conversions, stat.clicks)),
        commission=None if stat.commission is None else as_text(stat.commission),
        currency=stat.currency,
        epc=as_text(epc(stat.commission, stat.clicks)),
        ownership=stat.ownership,
        commission_reason=stat.commission_reason,
    )


def _assemble_sources(click_groups, conv_groups) -> tuple[list[SourceRow], str, str | None]:
    quality = "partial" if len(click_groups) > 500 else "reliable"
    reason = "source_groups_truncated" if quality == "partial" else None
    grouped: dict[str, dict] = {}
    for traffic_source, referer, clicks in click_groups[:500]:
        key, label, kind = classify_source(traffic_source, referer)
        bucket = grouped.setdefault(
            key,
            {"label": label, "kind": kind, "clicks": 0, "conversions": 0, "amounts": {}},
        )
        bucket["clicks"] += clicks
    for traffic_source, conversions, commission, currency, money_reason in conv_groups:
        key, label, kind = classify_source(traffic_source, None)
        bucket = grouped.setdefault(
            key,
            {"label": label, "kind": kind, "clicks": 0, "conversions": 0, "amounts": {}},
        )
        bucket["conversions"] += conversions
        if money_reason:
            bucket["money_reason"] = money_reason
        elif commission is not None and currency and commission != 0:
            bucket["amounts"][currency] = bucket["amounts"].get(currency, Decimal("0.00")) + commission
    total = sum(item["clicks"] for item in grouped.values())
    rows = []
    for key, item in grouped.items():
        amounts = {code: value for code, value in item["amounts"].items() if value != 0}
        if item.get("money_reason") or len(amounts) > 1:
            commission, currency, money_reason = None, None, item.get("money_reason") or "mixed_currency"
        elif amounts:
            currency, commission = next(iter(amounts.items()))
            commission = money(commission)
            money_reason = None
        else:
            commission, currency, money_reason = Decimal("0.00"), None, None
        rows.append(
            SourceRow(
                key=key,
                label=item["label"],
                kind=item["kind"],
                clicks=item["clicks"],
                conversions=item["conversions"],
                cr=as_text(ratio(item["conversions"], item["clicks"])),
                epc=as_text(epc(commission, item["clicks"])),
                commission=None if commission is None else as_text(commission),
                currency=currency,
                commission_reason=money_reason,
                share=as_text(ratio(item["clicks"], total)),
                roi=None,
                roi_reason=ROI_REASON,
            )
        )
    rows.sort(key=lambda item: item.clicks, reverse=True)
    return rows[:20], quality, reason


def _distribution(rows: list[SourceRow]) -> list[SourceRow]:
    visible = [row for row in rows if row.clicks > 0]
    if len(visible) <= 6:
        return visible
    head = visible[:5]
    tail = visible[5:]
    clicks = sum(item.clicks for item in tail)
    conversions = sum(item.conversions for item in tail)
    head.append(
        SourceRow(
            key="other",
            label="Остальные",
            kind="other",
            clicks=clicks,
            conversions=conversions,
            cr=as_text(ratio(conversions, clicks)),
            share=as_text(ratio(clicks, sum(item.clicks for item in visible))),
            roi=None,
            roi_reason=ROI_REASON,
        )
    )
    return head


async def build_overview(db, session_data, filt: AnalyticsFilters) -> OverviewResponse:
    scope = await prepare(db, session_data, filt)
    clickhouse = await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    if filt.postgres_blocked_reason:
        return OverviewResponse(
            meta=_meta(scope, filt, "unavailable" if clickhouse == "unavailable" else "ok"),
            kpis=_kpis_from_totals(None, None, filt.postgres_blocked_reason),
            timeseries=[],
            sources=[],
            source_total=0,
            source_quality="unavailable",
            source_reason=filt.postgres_blocked_reason,
            offers=[],
            efficiency=Efficiency(
                dimension="partners" if scope.role == "business" else "links",
                metric="cr",
                formula=EFFICIENCY_FORMULA,
                rows=[],
            ),
        )
    current = await repo.totals(db, scope, filt, start=filt.date_range.start, end=filt.date_range.end)
    previous = await _previous_totals(db, scope, filt)
    points = _series(await repo.timeseries(db, scope, filt, repo.granularity_for(filt.date_range.start, filt.date_range.end)))
    sources, source_quality, source_reason = _assemble_sources(
        await repo.click_sources(db, scope, filt),
        await repo.conversion_sources(db, scope, filt),
    )
    prefix = "/business" if scope.role == "business" else "/partner"
    offers = [_entity(item, f"{prefix}/offers/{item.entity_id}") for item in await repo.top_offers(db, scope, filt)]
    efficiency_rows = [_entity(item) for item in await repo.efficiency(db, scope, filt)]
    return OverviewResponse(
        meta=_meta(scope, filt, "ok" if clickhouse != "unavailable" else "unavailable"),
        kpis=_kpis_from_totals(current, previous, None),
        timeseries=points,
        sources=_distribution(sources),
        source_total=current.clicks,
        source_quality=source_quality,
        source_reason=source_reason,
        offers=offers,
        efficiency=Efficiency(
            dimension="partners" if scope.role == "business" else "links",
            metric="cr",
            formula=EFFICIENCY_FORMULA,
            rows=efficiency_rows,
        ),
    )


async def build_funnel(db, session_data, filt: AnalyticsFilters) -> FunnelResponse:
    scope = await prepare(db, session_data, filt)
    clickhouse = await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    blocked = filt.postgres_blocked_reason
    clicks = conversions = None
    statuses: dict[str, int] = {}
    if not blocked:
        current = await repo.totals(db, scope, filt, start=filt.date_range.start, end=filt.date_range.end)
        clicks = current.clicks
        conversions = current.conversions
        statuses = await repo.status_counts(db, scope, filt, filt.date_range.start, filt.date_range.end)
    reached, engaged = None, None
    reached_quality, reached_reason = "unavailable", "clickhouse_unavailable"
    ch_state = "unavailable" if clickhouse == "unavailable" else "ok"
    if clicks == 0:
        reached, engaged = 0, 0
        reached_quality, reached_reason = "reliable", None
    elif ch_state != "unavailable" or clickhouse != "unavailable":
        probe = filt
        exact_reason = None
        if not blocked and filt.rqcids is None:
            ids = await repo.click_rqcids(db, scope, filt, filt.date_range.start, filt.date_range.end)
            if ids is None:
                exact_reason = "rqcid_intersection_skipped"
            else:
                probe = replace(filt, rqcids=ids)
        elif blocked:
            probe = replace(filt, rqcids=None)
            exact_reason = blocked
        where, params = _where(scope, probe)
        ok, rows = await _ch(funnel_sql(where), params)
        if not ok:
            ch_state = "unavailable"
            reached_quality, reached_reason = "unavailable", "clickhouse_unavailable"
        else:
            row = _first(rows)
            reached = _whole(row.get("reached"))
            engaged = _whole(row.get("engaged"))
            reached_quality = "partial" if exact_reason else "reliable"
            reached_reason = exact_reason
    steps = [
        _step("clicks", "Клики", clicks, clicks, blocked is None, "reliable" if not blocked else "unavailable", blocked, DEFINITIONS["clicks"]),
        _step("reached", "Достигли сайта", reached, clicks, reached is not None, reached_quality, reached_reason, DEFINITIONS["reached"]),
        _step("engagement", "Вовлечение", engaged, clicks, engaged is not None, reached_quality, reached_reason, DEFINITIONS["engagement"]),
        _step("target", "Целевое действие", None, clicks, False, "unavailable", "target_action_not_configured", DEFINITIONS["target_action"]),
        _step("conversions", "Конверсии", conversions, clicks, blocked is None, "reliable" if not blocked else "unavailable", blocked, DEFINITIONS["conversions"]),
    ]
    return FunnelResponse(
        meta=_meta(scope, filt, ch_state),
        steps=steps,
        losses=_losses(steps),
        statuses=_statuses(statuses),
    )


def _step(key, label, value, base, available, quality, reason, definition) -> FunnelStep:
    return FunnelStep(
        key=key,
        label=label,
        value=None if value is None else str(value),
        rate=as_text(ratio(value, base)) if available else None,
        available=available and value is not None,
        quality=quality if available else "unavailable",
        reason=reason,
        definition=definition,
    )


def _losses(steps: list[FunnelStep]) -> list[FunnelLoss]:
    losses = []
    for left, right in zip(steps, steps[1:]):
        available = left.available and right.available and left.value not in (None, "0")
        retained = ratio(int(right.value), int(left.value)) if available and right.value is not None and left.value else None
        lost = None if retained is None else (Decimal("100") - retained).quantize(Decimal("0.01"))
        losses.append(
            FunnelLoss(
                from_label=left.label,
                to_label=right.label,
                retained=as_text(retained) if available else None,
                lost=as_text(lost) if available else None,
                available=available,
            )
        )
    return losses


def _statuses(counts: dict[str, int]) -> list[StatusSlice]:
    groups = (
        ("approved", "Подтверждено", ("approved", "paid")),
        ("pending", "В ожидании", ("pending",)),
        ("rejected", "Отклонено", ("rejected", "reversed")),
    )
    slices = []
    for key, label, names in groups:
        count = sum(counts.get(name, 0) for name in names)
        if count:
            slices.append(StatusSlice(key=key, label=label, count=count))
    return slices


async def build_behavior(db, session_data, filt: AnalyticsFilters) -> BehaviorResponse:
    scope = await prepare(db, session_data, filt)
    await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    bundle, clickhouse = await _behavior(scope, filt)
    pages, paths = [], []
    if clickhouse == "ok":
        where, params = _where(scope, filt)
        ok_pages, page_rows = await _ch(pages_sql(where), params)
        ok_paths, path_rows = await _ch(paths_sql(where), params)
        if ok_pages:
            pages = [
                PageRow(
                    page=normalize_page(row.get("path")) or "/",
                    views=_whole(row.get("views")),
                    engagement=as_text(ratio(_whole(row.get("engaged")), _whole(row.get("views")))),
                )
                for row in page_rows
                if _whole(row.get("views"))
            ]
        if ok_paths:
            paths = [
                PathEdge(
                    source=normalize_page(row.get("prev_path")) or "/",
                    target=normalize_page(row.get("path")) or "/",
                    value=_whole(row.get("transitions")),
                )
                for row in path_rows
                if _whole(row.get("transitions"))
            ]
        if not ok_pages or not ok_paths:
            clickhouse = "unavailable"
    return BehaviorResponse(meta=_meta(scope, filt, clickhouse), kpis=bundle["kpis"], scroll=bundle["scroll"], paths=paths, pages=pages)


async def build_sources(db, session_data, filt: AnalyticsFilters) -> SourcesResponse:
    scope = await prepare(db, session_data, filt)
    clickhouse = await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    if filt.postgres_blocked_reason:
        return SourcesResponse(
            meta=_meta(scope, filt, "unavailable" if clickhouse == "unavailable" else "ok"),
            points=[],
            distribution=[],
            rows=[],
            source_quality="unavailable",
            source_reason=filt.postgres_blocked_reason,
        )
    rows, quality, reason = _assemble_sources(
        await repo.click_sources(db, scope, filt),
        await repo.conversion_sources(db, scope, filt),
    )
    return SourcesResponse(
        meta=_meta(scope, filt, "ok" if clickhouse != "unavailable" else "unavailable"),
        points=[row for row in rows if row.epc is not None and row.clicks > 0],
        distribution=_distribution(rows),
        rows=rows,
        source_quality=quality,
        source_reason=reason,
    )


async def build_quality(db, session_data, filt: AnalyticsFilters) -> QualityResponse:
    scope = await prepare(db, session_data, filt)
    clickhouse = await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    blocked = filt.postgres_blocked_reason
    clicks = None
    click_map: dict[str, int] = {}
    if not blocked:
        current = await repo.totals(db, scope, filt, start=filt.date_range.start, end=filt.date_range.end)
        clicks = current.clicks
        click_map = await repo.click_buckets(
            db, scope, filt, repo.granularity_for(filt.date_range.start, filt.date_range.end)
        )
    bundle, ch_state = await _behavior(scope, filt)
    reached = None
    reached_quality, reached_reason = "unavailable", "clickhouse_unavailable"
    series = []
    comparison = []
    if clicks == 0:
        reached, reached_quality, reached_reason = 0, "reliable", None
    elif ch_state == "ok":
        where, params = _where(scope, filt)
        ok, rows = await _ch(funnel_sql(where), params)
        if ok:
            reached = _whole(_first(rows).get("reached"))
            reached_quality, reached_reason = "reliable", None
            if clicks is not None and reached > clicks:
                reached_quality, reached_reason = "partial", "reached_exceeds_clicks"
        else:
            ch_state = "unavailable"
        ok_series, series_rows = await _ch(quality_series_sql(where, filt.date_range.timezone), params)
        if ok_series:
            for row in series_rows:
                bucket = str(row.get("bucket"))
                day_clicks = click_map.get(bucket, 0)
                day_reached = _whole(row.get("reached"))
                day_sessions = _whole(row.get("sessions"))
                day_engaged = _whole(row.get("engaged"))
                rate = ratio(day_reached, day_clicks) if day_clicks else None
                series.append(
                    SeriesPoint(
                        bucket=bucket,
                        clicks=day_clicks,
                        reached=day_reached,
                        reached_rate=as_text(rate),
                        engagement=as_text(ratio(day_engaged, day_sessions)) if day_sessions else None,
                    )
                )
        else:
            ch_state = "unavailable"
        comparison = await _comparison(db, scope, filt, where, params)
    kpis = {
        "reached": _count(reached, quality=reached_quality, reason=reached_reason) if reached is not None else _missing(reached_reason),
        "engagement": bundle["kpis"]["engagement"],
        "bounce": bundle["kpis"]["bounce"],
        "duration": bundle["kpis"]["duration"],
        "pages_per_session": bundle["kpis"]["pages_per_session"],
    }
    if blocked:
        kpis["reached"] = _missing(blocked)
    return QualityResponse(
        meta=_meta(scope, filt, ch_state if clickhouse != "unavailable" else "unavailable"),
        kpis=kpis,
        series=series,
        comparison=comparison,
        dimension="partners" if scope.role == "business" else "links",
    )


async def build_performance(db, session_data, filt: AnalyticsFilters) -> PerformanceResponse:
    scope = await prepare(db, session_data, filt)
    await _constrain(scope, filt, filt.date_range.start, filt.date_range.end)
    where, params = _where(scope, filt)
    ok, rows = await _ch(performance_sql(where), params)
    series_ok, series_rows = await _ch(performance_series_sql(where, filt.date_range.timezone), params)
    pages_ok, page_rows = await _ch(slow_pages_sql(where), params)
    clickhouse = "ok" if ok and series_ok and pages_ok else "unavailable"
    row = _first(rows) if ok else {}
    kpis = {
        "lcp": _vital(row, "lcp", "milliseconds"),
        "inp": _vital(row, "inp", "milliseconds"),
        "cls": _vital(row, "cls", "score", places="0.001"),
        "weight": _vital(row, "weight", "bytes"),
        "load_errors": _load_errors(row) if ok else _missing("clickhouse_unavailable", "percent"),
    }
    if not ok:
        kpis = {key: _missing("clickhouse_unavailable", metric.unit or "count") for key, metric in kpis.items()}
    grouped: dict[str, dict] = {}
    if series_ok:
        for item in series_rows:
            bucket = str(item.get("bucket"))
            point = grouped.setdefault(bucket, {})
            group = str(item.get("device_group"))
            value = _float(item.get("lcp"))
            if group in {"mobile", "desktop"} and value is not None:
                point[group] = str(int(value))
    series = [
        SeriesPoint(bucket=bucket, mobile=values.get("mobile"), desktop=values.get("desktop"))
        for bucket, values in sorted(grouped.items())
    ]
    pages = []
    if pages_ok:
        for item in page_rows:
            lcp = _float(item.get("lcp"))
            weight = _float(item.get("weight"))
            pages.append(
                SlowPage(
                    page=normalize_page(item.get("path")) or "/",
                    lcp=None if lcp is None else str(int(lcp)),
                    weight=None if weight is None or weight <= 0 else str(int(weight)),
                    samples=_whole(item.get("samples")),
                )
            )
    return PerformanceResponse(meta=_meta(scope, filt, clickhouse), kpis=kpis, series=series, pages=pages)


async def build_filters(db, session_data) -> FiltersResponse:
    scope = await resolve_scope(db, session_data)
    options = await repo.filter_options(db, scope)
    return FiltersResponse(
        role=scope.role,
        offers=[FilterOption(**item) for item in options["offers"]],
        campaigns=[FilterOption(**item) for item in options["campaigns"]],
        links=[FilterOption(**item) for item in options["links"]],
        partners=[FilterOption(**item) for item in options["partners"]],
        sites=[FilterOption(**item) for item in options["sites"]],
        traffic_sources=[
            TrafficOption(code=code, label=catalog_label(code) or code) for code in options["traffic_sources"]
        ],
        devices=["mobile", "desktop", "tablet"],
    )


async def _behavior(scope: AnalyticsScope, filt: AnalyticsFilters) -> tuple[dict, str]:
    where, params = _where(scope, filt)
    basic_ok, basic_rows = await _ch(behavior_sql(where), params)
    session_ok, session_rows = await _ch(session_sql(where), params)
    depth_ok, depth_rows = await _ch(depth_sql(where), params)
    clickhouse = "ok" if basic_ok and session_ok and depth_ok else "unavailable"
    basic = _first(basic_rows) if basic_ok else {}
    sessions_row = _first(session_rows) if session_ok else {}
    depth_row = _first(depth_rows) if depth_ok else {}
    sessions = _whole(basic.get("sessions")) if basic_ok else None
    page_views = _whole(basic.get("page_views")) if basic_ok else None
    measurable = _whole(sessions_row.get("measurable")) if session_ok else 0
    engaged = _whole(sessions_row.get("engaged")) if session_ok else 0
    bounce_base = _whole(sessions_row.get("bounce_base")) if session_ok else 0
    bounced = _whole(sessions_row.get("bounced")) if session_ok else 0
    duration_sessions = _whole(sessions_row.get("duration_sessions")) if session_ok else 0
    scroll_views = _whole(basic.get("scroll_views")) if basic_ok else 0
    if not basic_ok or not session_ok:
        kpis = {
            "sessions": _missing("clickhouse_unavailable"),
            "engagement": _missing("clickhouse_unavailable", "percent"),
            "duration": _missing("clickhouse_unavailable", "milliseconds"),
            "depth": _missing("clickhouse_unavailable", "percent"),
            "bounce": _missing("clickhouse_unavailable", "percent"),
            "pages_per_session": _missing("clickhouse_unavailable", "ratio"),
        }
        scroll = [_scroll(milestone, None, "unavailable", "clickhouse_unavailable") for milestone in (25, 50, 75, 90, 100)]
        return {"kpis": kpis, "scroll": scroll}, "unavailable"
    engagement_quality = coverage_quality(measurable, sessions or 0)
    bounce_quality = coverage_quality(bounce_base, sessions or 0)
    duration_quality = coverage_quality(duration_sessions, sessions or 0)
    depth_samples = _whole(depth_row.get("samples")) if depth_ok else 0
    depth_quality = "unavailable" if not depth_ok or depth_samples == 0 else coverage_quality(scroll_views, page_views or 0)
    pages_quality = "reliable" if sessions else "unavailable"
    kpis = {
        "sessions": _count(sessions, quality="reliable" if sessions is not None else "unavailable"),
        "engagement": _rate(
            ratio(engaged, measurable) if measurable else None,
            quality=engagement_quality,
            reason=None if engagement_quality == "reliable" else "low_coverage",
            samples=measurable,
            coverage=ratio(measurable, sessions) if sessions else None,
        ),
        "duration": _rate(
            None if duration_sessions == 0 else Decimal(str(int(_float(sessions_row.get("avg_duration")) or 0))),
            quality=duration_quality,
            reason=None if duration_quality == "reliable" else "low_coverage",
            unit="milliseconds",
            samples=duration_sessions,
            coverage=ratio(duration_sessions, sessions) if sessions else None,
        ),
        "depth": _rate(
            None if depth_samples == 0 else decimal_or_none(_float(depth_row.get("depth"))),
            quality=depth_quality,
            reason=None if depth_quality == "reliable" else "low_coverage",
            samples=depth_samples,
            coverage=ratio(scroll_views, page_views) if page_views else None,
        ),
        "bounce": _rate(
            ratio(bounced, bounce_base) if bounce_base else None,
            quality=bounce_quality,
            reason=None if bounce_quality == "reliable" else "low_coverage",
            samples=bounce_base,
            coverage=ratio(bounce_base, sessions) if sessions else None,
        ),
        "pages_per_session": _rate(
            None if not sessions else (Decimal(page_views or 0) / Decimal(sessions)).quantize(Decimal("0.01")),
            quality=pages_quality,
            reason=None if sessions else "no_sessions",
            unit="ratio",
        ),
    }
    scroll_quality = "unavailable" if scroll_views == 0 else coverage_quality(scroll_views, page_views or 0)
    scroll_reason = None if scroll_quality == "reliable" else "low_coverage"
    scroll = []
    for milestone in (25, 50, 75, 90, 100):
        observed = _whole(basic.get(f"m{milestone}"))
        scroll.append(
            _scroll(
                milestone,
                ratio(observed, scroll_views) if scroll_views else None,
                scroll_quality,
                None if scroll_views else "no_scroll_events",
            )
            if scroll_quality != "partial"
            else _scroll(milestone, ratio(observed, scroll_views) if scroll_views else None, scroll_quality, scroll_reason)
        )
    return {"kpis": kpis, "scroll": scroll}, clickhouse


def _scroll(milestone: int, value: Decimal | None, quality: str, reason: str | None) -> ScrollPoint:
    return ScrollPoint(milestone=milestone, value=as_text(value) if quality != "unavailable" else None, quality=quality, reason=reason)


async def _comparison(db, scope, filt, where: str, params: dict) -> list[EntityRow]:
    stats = await repo.comparison_base(db, scope, filt)
    column = "partner_id" if scope.role == "business" else "tracking_link_id"
    ok, rows = await _ch(comparison_sql(where, column), params)
    found = {}
    if ok:
        for row in rows:
            entity_id = _whole(row.get("entity_id"))
            found[None if entity_id == 0 else entity_id] = row
    result = []
    for stat in stats:
        sample = found.get(stat.entity_id, {})
        clicks = stat.clicks
        reached = _whole(sample.get("reached")) if ok else None
        sessions = _whole(sample.get("sessions")) if ok else None
        engaged = _whole(sample.get("engaged")) if ok else None
        entity = _entity(stat)
        if not ok:
            entity.quality = "unavailable"
        else:
            entity.reached_rate = as_text(ratio(reached, clicks)) if clicks else None
            entity.engagement = as_text(ratio(engaged, sessions)) if sessions else None
            if reached is not None and clicks and reached > clicks:
                entity.quality = "partial"
        result.append(entity)
    return result


def _vital(row: dict, key: str, unit: str, places: str = "1") -> Metric:
    samples = _whole(row.get(f"{key}_samples"))
    value = _float(row.get(key))
    if samples <= 0 or value is None:
        return _missing("no_measurements", unit)
    if unit == "score":
        quantized = decimal_or_none(value)
        quantized = None if quantized is None else quantized.quantize(Decimal(places))
        return _rate(quantized, quality="reliable", unit=unit, samples=samples)
    return _count(int(value), quality="reliable", reason=None).model_copy(update={"unit": unit, "samples": samples})


def _load_errors(row: dict) -> Metric:
    measured = _whole(row.get("measured"))
    failed = _whole(row.get("failed"))
    if measured <= 0:
        return _missing("no_measurements", "percent")
    return _rate(ratio(failed, measured), quality="reliable", samples=measured, unit="percent")
