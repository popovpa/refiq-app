from __future__ import annotations

import re
from datetime import datetime

from app.common.date_range import resolve_iana_timezone
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.analytics.metrics import MAX_CLS, MAX_VITAL_MS, MAX_WEIGHT_BYTES

_RQCID = re.compile(r"^[a-z0-9]{12}$")
_TZ = re.compile(r"^[A-Za-z0-9_+\-/]{1,64}$")

DEVICE_GROUPS = {
    "mobile": ("mobile", "phone"),
    "tablet": ("tablet",),
    "desktop": ("desktop", "pc"),
}

INTERACTION = """
(
    event_type = 'click'
    OR event_type = 'form_submit'
    OR (
        event_type = 'scroll'
        AND (
            scroll_milestone >= 25
            OR scroll_max_depth >= 10
            OR (scroll_max_depth > 0 AND scroll_max_depth <= 1 AND scroll_max_depth >= 0.1)
        )
    )
    OR (
        event_type = 'page_engagement'
        AND (
            engagement_click_count > 0
            OR engagement_scroll_count > 0
            OR engagement_active_duration > 0
        )
    )
)
"""

SCROLL_DEPTH = """
if(
    scroll_max_depth >= 0 AND scroll_max_depth <= 1,
    scroll_max_depth * 100,
    scroll_max_depth
)
"""


def ch_timezone(name: str) -> str:
    zone = resolve_iana_timezone(name)
    if not _TZ.match(zone):
        return "UTC"
    return zone


def day_expr(timezone_name: str) -> str:
    zone = ch_timezone(timezone_name)
    return f"toDate(toDateTime(intDiv(captured_ts, 1000), '{zone}'))"


def rqcid_sql(ids: list[str]) -> str:
    clean = [item for item in ids if _RQCID.match(item)]
    if not clean:
        return "''"
    return ",".join(f"'{item}'" for item in clean)


def int_sql(values: list[int]) -> str:
    return ",".join(str(int(item)) for item in values) or "0"


def scope_clause(
    *,
    role: str,
    business_id: int | None,
    partner_id: int | None,
    filt: AnalyticsFilters,
    start: datetime,
    end: datetime,
) -> tuple[str, dict]:
    params: dict = {
        "start_ms": int(start.timestamp() * 1000),
        "end_ms": int(end.timestamp() * 1000),
    }
    parts = [
        "captured_ts >= {start_ms:Int64}",
        "captured_ts <= {end_ms:Int64}",
    ]
    if role == "business":
        params["business_id"] = int(business_id or 0)
        parts.append("business_id = {business_id:Int64}")
    else:
        params["partner_id"] = int(partner_id or 0)
        parts.append("partner_id = {partner_id:Int64}")
    if filt.offer_id is not None:
        params["offer_id"] = filt.offer_id
        parts.append("offer_id = {offer_id:Int64}")
    if filt.campaign_id is not None:
        params["campaign_id"] = filt.campaign_id
        parts.append("campaign_id = {campaign_id:Int64}")
    if filt.link_id is not None:
        params["link_id"] = filt.link_id
        parts.append("tracking_link_id = {link_id:Int64}")
    if filt.partner_id is not None and role == "business":
        params["filter_partner_id"] = filt.partner_id
        parts.append("partner_id = {filter_partner_id:Int64}")
    if filt.site_id is not None:
        params["site_id"] = filt.site_id
        parts.append("site_id = {site_id:Int64}")
    if filt.landing:
        params["landing"] = filt.landing
        parts.append("page_pathname = {landing:String}")
    if filt.utm_source:
        params["utm_source"] = filt.utm_source
        parts.append("utm_source = {utm_source:String}")
    if filt.utm_campaign:
        params["utm_campaign"] = filt.utm_campaign
        parts.append("utm_campaign = {utm_campaign:String}")
    if filt.device:
        group = DEVICE_GROUPS.get(filt.device)
        if group:
            parts.append("device_type IN (" + ",".join(f"'{item}'" for item in group) + ")")
        else:
            params["device"] = filt.device
            parts.append("device_type = {device:String}")
    if filt.rqcids is not None:
        parts.append(f"rqcid IN ({rqcid_sql(filt.rqcids)})")
    return " AND ".join(parts), params


def funnel_sql(where: str) -> str:
    return f"""
        SELECT
            uniqExactIf(rqcid, event_type = 'page_view' AND rqcid != '') AS reached,
            uniqExactIf(rqcid, rqcid != '' AND {INTERACTION}) AS engaged
        FROM clickstream_events
        WHERE {where}
    """


def behavior_sql(where: str) -> str:
    return f"""
        SELECT
            uniqExactIf(session_id, event_type = 'page_view' AND session_id != 0) AS sessions,
            uniqExactIf(page_view_id, event_type = 'page_view' AND page_view_id != 0) AS page_views,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone > 0 OR scroll_max_depth >= 0)) AS scroll_views,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone >= 25 OR {SCROLL_DEPTH} >= 25)) AS m25,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone >= 50 OR {SCROLL_DEPTH} >= 50)) AS m50,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone >= 75 OR {SCROLL_DEPTH} >= 75)) AS m75,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone >= 90 OR {SCROLL_DEPTH} >= 90)) AS m90,
            uniqExactIf(page_view_id, event_type = 'scroll' AND page_view_id != 0 AND (scroll_milestone >= 100 OR {SCROLL_DEPTH} >= 100)) AS m100
        FROM clickstream_events
        WHERE {where}
    """


def session_sql(where: str) -> str:
    return f"""
        SELECT
            count() AS sessions,
            countIf(has_engagement = 1 OR is_engaged = 1) AS measurable,
            countIf(is_engaged = 1) AS engaged,
            countIf(has_engagement = 1) AS bounce_base,
            countIf(has_engagement = 1 AND is_engaged = 0) AS bounced,
            countIf(active_duration > 0) AS duration_sessions,
            avgIf(active_duration, active_duration > 0) AS avg_duration
        FROM (
            SELECT
                session_id,
                max(event_type = 'page_engagement') AS has_engagement,
                max({INTERACTION}) AS is_engaged,
                maxIf(
                    engagement_active_duration,
                    event_type = 'page_engagement' AND engagement_active_duration > 0
                ) AS active_duration
            FROM clickstream_events
            WHERE {where} AND session_id != 0
            GROUP BY session_id
        ) AS per_session
    """


def depth_sql(where: str) -> str:
    return f"""
        SELECT avg(observed_depth) AS depth, count() AS samples
        FROM (
            SELECT
                page_view_id,
                max({SCROLL_DEPTH}) AS observed_depth
            FROM clickstream_events
            WHERE {where}
              AND event_type = 'scroll'
              AND page_view_id != 0
              AND scroll_max_depth >= 0
            GROUP BY page_view_id
        ) AS per_view
    """


def pages_sql(where: str) -> str:
    return f"""
        SELECT
            path,
            count() AS views,
            countIf(is_engaged = 1) AS engaged
        FROM (
            SELECT
                page_view_id,
                argMin(page_pathname, captured_ts) AS path,
                max({INTERACTION}) AS is_engaged
            FROM clickstream_events
            WHERE {where} AND page_view_id != 0 AND (event_type = 'page_view' OR {INTERACTION})
            GROUP BY page_view_id
        ) AS per_view
        GROUP BY path
        ORDER BY views DESC
        LIMIT 15
    """


def paths_sql(where: str) -> str:
    return f"""
        SELECT prev_path, path, count() AS transitions
        FROM (
            SELECT
                path,
                lagInFrame(path) OVER (
                    PARTITION BY session_id
                    ORDER BY started, page_view_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS prev_path
            FROM (
                SELECT
                    session_id,
                    page_view_id,
                    argMin(page_pathname, captured_ts) AS path,
                    min(if(page_view_started_ts > 0, page_view_started_ts, captured_ts)) AS started
                FROM clickstream_events
                WHERE {where}
                  AND event_type = 'page_view'
                  AND session_id != 0
                  AND page_view_id != 0
                GROUP BY session_id, page_view_id
            ) AS page_views
        ) AS ordered_views
        WHERE prev_path != '' AND path != '' AND prev_path != path
        GROUP BY prev_path, path
        ORDER BY transitions DESC
        LIMIT 12
    """


def quality_series_sql(where: str, timezone_name: str) -> str:
    day = day_expr(timezone_name)
    return f"""
        SELECT
            {day} AS bucket,
            uniqExactIf(rqcid, event_type = 'page_view' AND rqcid != '') AS reached,
            uniqExactIf(session_id, event_type = 'page_view' AND session_id != 0) AS sessions,
            uniqExactIf(session_id, session_id != 0 AND {INTERACTION}) AS engaged
        FROM clickstream_events
        WHERE {where}
        GROUP BY bucket
        ORDER BY bucket
        LIMIT 120
    """


def comparison_sql(where: str, column: str) -> str:
    if column not in {"partner_id", "tracking_link_id"}:
        raise ValueError("unsupported comparison column")
    return f"""
        SELECT
            {column} AS entity_id,
            uniqExactIf(rqcid, event_type = 'page_view' AND rqcid != '') AS reached,
            uniqExactIf(session_id, event_type = 'page_view' AND session_id != 0) AS sessions,
            uniqExactIf(session_id, session_id != 0 AND {INTERACTION}) AS engaged
        FROM clickstream_events
        WHERE {where}
        GROUP BY entity_id
        ORDER BY reached DESC
        LIMIT 50
    """


def performance_sql(where: str) -> str:
    lcp_ok = f"web_vital_lcp > 0 AND web_vital_lcp < {MAX_VITAL_MS}"
    inp_ok = f"web_vital_inp > 0 AND web_vital_inp < {MAX_VITAL_MS}"
    cls_ok = f"web_vital_cls >= 0 AND web_vital_cls <= {MAX_CLS}"
    weight_ok = (
        f"(performance_transfer_size > 0 AND performance_transfer_size < {MAX_WEIGHT_BYTES})"
        f" OR (resource_transfer_bytes > 0 AND resource_transfer_bytes < {MAX_WEIGHT_BYTES})"
    )
    return f"""
        SELECT
            quantile(0.75)(lcp_value) AS lcp,
            countIf(lcp_value IS NOT NULL) AS lcp_samples,
            quantile(0.75)(inp_value) AS inp,
            countIf(inp_value IS NOT NULL) AS inp_samples,
            quantile(0.75)(cls_value) AS cls,
            countIf(cls_value IS NOT NULL) AS cls_samples,
            quantile(0.75)(weight_value) AS weight,
            countIf(weight_value IS NOT NULL) AS weight_samples,
            countIf(measured = 1) AS measured,
            countIf(failed = 1) AS failed
        FROM (
            SELECT
                page_view_id,
                if(max({lcp_ok}) = 0, NULL, argMaxIf(web_vital_lcp, captured_ts, {lcp_ok})) AS lcp_value,
                if(max({inp_ok}) = 0, NULL, argMaxIf(web_vital_inp, captured_ts, {inp_ok})) AS inp_value,
                if(max({cls_ok}) = 0, NULL, argMaxIf(web_vital_cls, captured_ts, {cls_ok})) AS cls_value,
                if(
                    max({weight_ok}) = 0,
                    NULL,
                    argMaxIf(
                        if(performance_transfer_size > 0, performance_transfer_size, resource_transfer_bytes),
                        captured_ts,
                        {weight_ok}
                    )
                ) AS weight_value,
                max(resource_count > 0 OR resource_failed_count > 0) AS measured,
                max(resource_failed_count > 0) AS failed
            FROM clickstream_events
            WHERE {where} AND event_type = 'page_performance' AND page_view_id != 0
            GROUP BY page_view_id
        ) AS per_view
    """


def performance_series_sql(where: str, timezone_name: str) -> str:
    day = day_expr(timezone_name)
    return f"""
        SELECT bucket, device_group, quantile(0.75)(lcp_value) AS lcp
        FROM (
            SELECT
                {day} AS bucket,
                page_view_id,
                multiIf(
                    device_type IN ('mobile', 'phone'), 'mobile',
                    device_type IN ('desktop', 'pc'), 'desktop',
                    'other'
                ) AS device_group,
                argMax(web_vital_lcp, captured_ts) AS lcp_value
            FROM clickstream_events
            WHERE {where}
              AND event_type = 'page_performance'
              AND page_view_id != 0
              AND web_vital_lcp > 0
              AND web_vital_lcp < {MAX_VITAL_MS}
            GROUP BY bucket, page_view_id, device_group
        ) AS per_view
        WHERE device_group IN ('mobile', 'desktop')
        GROUP BY bucket, device_group
        ORDER BY bucket
        LIMIT 240
    """


def slow_pages_sql(where: str) -> str:
    return f"""
        SELECT path, quantile(0.75)(lcp_value) AS lcp, quantile(0.75)(weight_value) AS weight, count() AS samples
        FROM (
            SELECT
                page_view_id,
                argMin(page_pathname, captured_ts) AS path,
                argMax(web_vital_lcp, captured_ts) AS lcp_value,
                argMax(
                    if(performance_transfer_size > 0, performance_transfer_size, resource_transfer_bytes),
                    captured_ts
                ) AS weight_value
            FROM clickstream_events
            WHERE {where}
              AND event_type = 'page_performance'
              AND page_view_id != 0
              AND web_vital_lcp > 0
              AND web_vital_lcp < {MAX_VITAL_MS}
            GROUP BY page_view_id
        ) AS per_view
        GROUP BY path
        ORDER BY lcp DESC
        LIMIT 10
    """


def rqcid_sql_query(where: str) -> str:
    return f"""
        SELECT rqcid
        FROM clickstream_events
        WHERE {where} AND rqcid != ''
        GROUP BY rqcid
        LIMIT {8001}
    """
