from __future__ import annotations

import re
from typing import Any

_REDACTED = "[redacted]"

_SECRET_KEYS = {
    "password",
    "password_hash",
    "token",
    "secret",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
    "authorization",
    "provider_token",
}

_SECRET_PARTS = {
    "password",
    "token",
    "secret",
    "authorization",
}

_CAMEL_BOUNDARY = re.compile(r"([A-Z])")
_SPLIT = re.compile(r"[^a-z0-9]+")


def _normalize_key(key: str) -> str:
    return _CAMEL_BOUNDARY.sub(r"_\1", str(key)).lower().strip("_")


def is_sensitive_key(key: str) -> bool:
    lowered = _normalize_key(key)
    if lowered in _SECRET_KEYS:
        return True
    parts = [part for part in _SPLIT.split(lowered) if part]
    if any(part in _SECRET_PARTS for part in parts):
        return True
    joined = "_".join(parts)
    return any(joined.endswith(f"_{item}") or joined == item for item in _SECRET_KEYS)


def sanitize_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, dict):
        return {str(item_key): sanitize_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item, key=key) for item in value]
    return value


def sanitize_payload(payload: dict | None) -> dict | None:
    if not payload:
        return None
    return sanitize_value(payload)
