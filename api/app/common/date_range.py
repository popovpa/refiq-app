from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_RANGE_DAYS = 366


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_iana_timezone(name: str | None) -> str:
    if not name:
        return "UTC"
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        return "UTC"
    return name


class ResolvedDateRange:
    def __init__(self, start: datetime, end: datetime, timezone_name: str):
        self.start = ensure_utc(start)
        self.end = ensure_utc(end)
        if self.end < self.start:
            self.start, self.end = self.end, self.start
        self.timezone = timezone_name

    @property
    def previous_start(self) -> datetime:
        return self.start - (self.end - self.start)

    @property
    def previous_end(self) -> datetime:
        return self.start


def default_days_range(days: int, now: datetime | None = None) -> ResolvedDateRange:
    current = ensure_utc(now or datetime.now(timezone.utc))
    start = (current - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return ResolvedDateRange(start, current, "UTC")


def resolve_query_range(
    date_from: datetime | None,
    date_to: datetime | None,
    timezone_name: str | None,
    days: int | None,
    *,
    now: datetime | None = None,
    default_days: int = 7,
) -> ResolvedDateRange:
    tz_name = resolve_iana_timezone(timezone_name)
    if date_from is not None and date_to is not None:
        start = ensure_utc(date_from)
        end = ensure_utc(date_to)
        if (end - start) > timedelta(days=MAX_RANGE_DAYS):
            end = start + timedelta(days=MAX_RANGE_DAYS)
        return ResolvedDateRange(start, end, tz_name)
    return default_days_range(days or default_days, now=now)


def local_dates(start: datetime, end: datetime, timezone_name: str) -> list:
    tz = ZoneInfo(resolve_iana_timezone(timezone_name))
    start_d = ensure_utc(start).astimezone(tz).date()
    end_d = ensure_utc(end).astimezone(tz).date()
    if end_d < start_d:
        return []
    days = []
    cursor = start_d
    while cursor <= end_d:
        days.append(cursor)
        cursor += timedelta(days=1)
        if len(days) > MAX_RANGE_DAYS:
            break
    return days


def local_day_key(value: datetime, timezone_name: str) -> str:
    tz = ZoneInfo(resolve_iana_timezone(timezone_name))
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(tz).date().isoformat()
