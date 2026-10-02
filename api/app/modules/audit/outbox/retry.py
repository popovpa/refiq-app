"""Bounded retry delays for unpublished outbox rows.

The schedule is 1, 5, 15, 30, 60 times the configured base delay.
Attempts after the last step stay at the last delay. Rows are never deleted on failure.
"""

_SCHEDULE = (1, 5, 15, 30, 60)


def retry_delay_seconds(attempt: int, *, base_delay: float) -> float:
    step = _SCHEDULE[min(max(attempt, 1), len(_SCHEDULE)) - 1]
    return max(base_delay, 0.0) * step
