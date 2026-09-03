from datetime import datetime, timezone

from app.common.date_range import resolve_query_range


def test_resolve_query_range_uses_explicit_utc_bounds():
    start = datetime(2026, 8, 31, 21, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    resolved = resolve_query_range(start, end, "Europe/Moscow", None)
    assert resolved.start == start
    assert resolved.end == end
    assert resolved.timezone == "Europe/Moscow"


def test_resolve_query_range_days_fallback_keeps_compat():
    now = datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    resolved = resolve_query_range(None, None, None, 7, now=now)
    assert resolved.timezone == "UTC"
    assert resolved.start == datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
    assert resolved.end == now
