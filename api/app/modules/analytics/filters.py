from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Query

from app.common.date_range import MAX_RANGE_DAYS, ResolvedDateRange, ensure_utc, resolve_query_range
from app.common.enums import ConversionStatus
from app.core.exceptions import AppError
from app.core.ids import parse_optional_id
from app.modules.analytics.metrics import COMMISSION_STATUSES, COUNT_STATUSES

_STATUS_VALUES = {item.value for item in ConversionStatus}
_DEVICE_GROUPS = {"mobile", "desktop", "tablet"}


@dataclass
class AnalyticsFilters:
    date_range: ResolvedDateRange
    offer_id: int | None
    campaign_id: int | None
    partner_id: int | None
    link_id: int | None
    site_id: int | None
    traffic_source: str | None
    device: str | None
    landing: str | None
    utm_source: str | None
    utm_campaign: str | None
    count_statuses: tuple[str, ...]
    commission_statuses: tuple[str, ...]
    statuses_explicit: bool
    rqcids: list[str] | None = None
    postgres_blocked_reason: str | None = None

    @property
    def needs_intersection(self) -> bool:
        return bool(self.device or self.landing or self.utm_source or self.utm_campaign or self.site_id)


def _clean_text(value: str | None, limit: int, field: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > limit or any(ord(char) < 32 for char in text):
        raise AppError("VALIDATION_ERROR", f"Invalid {field}", 400)
    return text


def _parse_id(value: str | None, field: str) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        return parse_optional_id(value)
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", f"Invalid {field}", 400) from exc


def _statuses(value: str | None) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    if value is None or not value.strip():
        return COUNT_STATUSES, COMMISSION_STATUSES, False
    parsed: list[str] = []
    for item in value.split(","):
        status = item.strip().lower()
        if not status:
            continue
        if status not in _STATUS_VALUES or status in parsed:
            raise AppError("VALIDATION_ERROR", "Invalid conversion status", 400)
        parsed.append(status)
    if not parsed:
        return COUNT_STATUSES, COMMISSION_STATUSES, False
    statuses = tuple(parsed)
    return statuses, statuses, True


def analytics_filters(
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    offer_id: str | None = None,
    campaign_id: str | None = None,
    partner_id: str | None = None,
    link_id: str | None = None,
    site_id: str | None = None,
    traffic_source: str | None = None,
    device: str | None = None,
    landing: str | None = None,
    utm_source: str | None = None,
    utm_campaign: str | None = None,
    statuses: str | None = None,
) -> AnalyticsFilters:
    if date_from is not None and date_to is not None:
        span = abs(ensure_utc(date_to) - ensure_utc(date_from))
        if span > timedelta(days=MAX_RANGE_DAYS):
            raise AppError(
                "ANALYTICS_RANGE_TOO_LARGE",
                "Date range cannot exceed 366 days",
                400,
            )
    date_range = resolve_query_range(
        date_from,
        date_to,
        timezone_name,
        None,
        now=datetime.now(timezone.utc),
        default_days=30,
    )
    device_text = _clean_text(device, 32, "device")
    if device_text and device_text not in _DEVICE_GROUPS and not device_text.replace("_", "").isalnum():
        raise AppError("VALIDATION_ERROR", "Invalid device", 400)
    count_statuses, commission_statuses, explicit = _statuses(statuses)
    return AnalyticsFilters(
        date_range=date_range,
        offer_id=_parse_id(offer_id, "offer"),
        campaign_id=_parse_id(campaign_id, "campaign"),
        partner_id=_parse_id(partner_id, "partner"),
        link_id=_parse_id(link_id, "link"),
        site_id=_parse_id(site_id, "site"),
        traffic_source=_clean_text(traffic_source, 80, "traffic source"),
        device=device_text,
        landing=_clean_text(landing, 300, "landing"),
        utm_source=_clean_text(utm_source, 120, "utm source"),
        utm_campaign=_clean_text(utm_campaign, 120, "utm campaign"),
        count_statuses=count_statuses,
        commission_statuses=commission_statuses,
        statuses_explicit=explicit,
    )
