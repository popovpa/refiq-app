from __future__ import annotations

from typing import Any

from sqlalchemy import inspect

from app.modules.audit.diff import clone_value, jsonable
from app.modules.audit.sanitizer import sanitize_payload
from app.modules.offers.models import Offer

# Business fields of Offer. This is an allowlist: anything else stays out of Kafka.
SNAPSHOT_FIELDS = (
    "business_id",
    "product_id",
    "name",
    "description",
    "image_url",
    "category",
    "category_id",
    "geo",
    "hold_period_days",
    "status",
    "visibility",
    "access_policy",
    "conversion_type",
    "attribution_window_days",
    "currency",
    "allowed_traffic",
    "forbidden_traffic",
    "partner_notes",
    "materials",
    "terms_version",
)

CAMEL_FIELDS = {
    "business_id": "businessId",
    "product_id": "productId",
    "name": "name",
    "description": "description",
    "image_url": "imageUrl",
    "category": "category",
    "category_id": "categoryId",
    "geo": "geo",
    "hold_period_days": "holdPeriodDays",
    "status": "status",
    "visibility": "visibility",
    "access_policy": "accessPolicy",
    "conversion_type": "conversionType",
    "attribution_window_days": "attributionWindowDays",
    "currency": "currency",
    "allowed_traffic": "allowedTraffic",
    "forbidden_traffic": "forbiddenTraffic",
    "partner_notes": "partnerNotes",
    "materials": "materials",
    "terms_version": "termsVersion",
    "commission_rules": "commissionRules",
}


def commission_rules_state(offer: Offer) -> list[dict[str, Any]]:
    # Do not lazy-load. Callers that already loaded the relationship contribute rules;
    # an unloaded collection must not open IO from a sync snapshot.
    if "commission_rules" in inspect(offer).unloaded:
        return []
    rules = offer.commission_rules or []
    return [
        {
            "type": rule.type,
            "value": float(rule.value),
            "currency": rule.currency,
        }
        for rule in rules
    ]


def kafka_state(offer: Offer) -> dict[str, Any]:
    state = {
        CAMEL_FIELDS[field]: jsonable(clone_value(getattr(offer, field)))
        for field in SNAPSHOT_FIELDS
    }
    state["commissionRules"] = commission_rules_state(offer)
    return sanitize_payload(state) or {}


def kafka_changes(changes: dict[str, dict]) -> dict[str, dict[str, Any]]:
    converted: dict[str, dict[str, Any]] = {}
    for key, diff in changes.items():
        name = CAMEL_FIELDS.get(key)
        if name is None or not isinstance(diff, dict):
            continue
        converted[name] = {
            "before": jsonable(diff.get("before")),
            "after": jsonable(diff.get("after")),
        }
    return sanitize_payload(converted) or {}
