from __future__ import annotations

import sys
import traceback

import structlog

logger = structlog.get_logger()


def email_domain(address: str) -> str:
    if "@" not in address:
        return "unknown"
    return address.rsplit("@", 1)[-1]


def log_email_error(event: str, exc: BaseException, **fields) -> None:
    payload = {
        "error_type": type(exc).__name__,
        "error": str(exc),
        **fields,
    }
    if exc.__cause__ is not None:
        payload["cause_type"] = type(exc.__cause__).__name__
        payload["cause"] = str(exc.__cause__)
    logger.error(event, exc_info=exc, **payload)
    extras = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    cause = exc.__cause__
    cause_text = f" caused by {type(cause).__name__}: {cause}" if cause else ""
    print(
        f"[email] {event} {extras} {type(exc).__name__}: {exc}{cause_text}".strip(),
        file=sys.stderr,
        flush=True,
    )
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
