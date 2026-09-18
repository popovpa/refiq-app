from collections import defaultdict

_COUNTERS: dict[str, int] = defaultdict(int)


def inc(name: str, n: int = 1) -> None:
    _COUNTERS[name] += n


def snapshot() -> dict[str, int]:
    return dict(_COUNTERS)


def reset() -> None:
    _COUNTERS.clear()
