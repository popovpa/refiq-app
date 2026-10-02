from collections import defaultdict

PENDING = "outbox.pending"
PUBLISHED = "outbox.published"
ERRORS = "outbox.publish.errors"
RETRIES = "outbox.retries"
LATENCY = "outbox.publish.latency"
OLDEST_PENDING_AGE = "outbox.oldest.pending.age"

_COUNTERS: dict[str, int] = defaultdict(int)
_GAUGES: dict[str, float] = {}


def inc(name: str, n: int = 1) -> None:
    _COUNTERS[name] += n


def set_gauge(name: str, value: float) -> None:
    _GAUGES[name] = float(value)


def snapshot() -> dict[str, float]:
    return {**_COUNTERS, **_GAUGES}


def reset() -> None:
    _COUNTERS.clear()
    _GAUGES.clear()
