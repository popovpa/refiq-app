from __future__ import annotations

import json
from typing import Any

from app.modules.ai.offer_fields import TRAFFIC_TYPES

_BUSINESS_ASK = (
    "комисс",
    "commission",
    "вознагражд",
    "атрибуц",
    "attribution",
    "окно атрибуц",
    "conversion",
    "конверси",
    "целев",
    "access_policy",
    "тип доступа",
    "invite",
    "одобрен",
)
_BUSINESS_NEGATION = (
    "не меняй",
    "не изменяй",
    "don't change",
    "do not change",
    "комиссию не",
    "условия не",
)


def instruction_allows_business_rules(instruction: str) -> bool:
    text = instruction.lower()
    if any(token in text for token in _BUSINESS_NEGATION):
        return False
    return any(token in text for token in _BUSINESS_ASK)


def parse_change_value(field: str, raw: Any) -> Any:
    if field in {"allowed_traffic", "forbidden_traffic"}:
        return _parse_traffic(raw)
    if field == "commission_value":
        return float(raw)
    if field == "attribution_window_days":
        return int(float(raw))
    if isinstance(raw, str):
        return raw.strip()
    return raw


def _parse_traffic(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [item for item in raw if item in TRAFFIC_TYPES]
    if not isinstance(raw, str):
        return []
    text = raw.strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            return [item for item in loaded if item in TRAFFIC_TYPES]
    except ValueError:
        pass
    return [part.strip() for part in text.split(",") if part.strip() in TRAFFIC_TYPES]


def values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, list) or isinstance(right, list):
        return [str(item) for item in (left or [])] == [str(item) for item in (right or [])]
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return float(left) == float(right)
        except (TypeError, ValueError):
            return False
    return ("" if left is None else str(left)) == ("" if right is None else str(right))


def serialize_value(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    return value
