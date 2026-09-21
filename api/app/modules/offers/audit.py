from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.context import AuditContext
from app.modules.audit.diff import clone_value, field_changes
from app.modules.audit.events import EntityType, OfferEventType
from app.modules.audit.service import audit_service
from app.modules.offers.models import Offer

CREATE_FIELDS = (
    "status",
    "product_id",
    "hold_period_days",
    "access_policy",
    "visibility",
    "conversion_type",
    "currency",
    "geo",
    "allowed_traffic",
    "attribution_window_days",
    "name",
)

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

SPECIALIZED_EVENTS: tuple[tuple[str, frozenset[str]], ...] = (
    (OfferEventType.STATUS_CHANGED, frozenset({"status"})),
    (OfferEventType.HOLD_CHANGED, frozenset({"hold_period_days"})),
    (OfferEventType.TRAFFIC_POLICY_CHANGED, frozenset({"geo", "allowed_traffic", "forbidden_traffic"})),
    (OfferEventType.ACCESS_POLICY_CHANGED, frozenset({"access_policy", "visibility"})),
    (OfferEventType.PRODUCT_CHANGED, frozenset({"product_id"})),
)


def snapshot_offer(offer: Offer) -> dict[str, Any]:
    return {field: clone_value(getattr(offer, field)) for field in SNAPSHOT_FIELDS}


def offer_metadata(offer: Offer) -> dict[str, int | None]:
    metadata: dict[str, int | None] = {"business_id": offer.business_id}
    if offer.product_id is not None:
        metadata["product_id"] = offer.product_id
    return metadata


def classify_offer_changes(before: dict, after: dict) -> list[tuple[str, dict]]:
    changes = field_changes(before, after, SNAPSHOT_FIELDS)
    if not changes:
        return []

    events: list[tuple[str, dict]] = []
    remaining = set(changes)
    for event_type, fields in SPECIALIZED_EVENTS:
        matched = {field: changes[field] for field in fields if field in changes}
        if not matched:
            continue
        events.append((event_type, matched))
        remaining -= set(matched)

    ordinary = {field: changes[field] for field in remaining}
    if ordinary:
        events.append((OfferEventType.UPDATED, ordinary))
    return events


async def record_offer_created(
    session: AsyncSession,
    offer: Offer,
    context: AuditContext,
    *,
    source_operation: str = "offers.create",
) -> None:
    blank = {field: None for field in CREATE_FIELDS}
    current = {field: clone_value(getattr(offer, field)) for field in CREATE_FIELDS}
    changes = field_changes(blank, current, CREATE_FIELDS)
    await audit_service.record(
        session,
        event_type=OfferEventType.CREATED,
        entity_type=EntityType.OFFER,
        entity_id=offer.id,
        context=context,
        changes=changes,
        metadata=offer_metadata(offer),
        source_operation=source_operation,
    )


async def record_offer_mutations(
    session: AsyncSession,
    offer: Offer,
    before: dict,
    after: dict,
    context: AuditContext,
    *,
    source_operation: str = "offers.update",
    reason: str | None = None,
) -> int:
    events = classify_offer_changes(before, after)
    for event_type, changes in events:
        await audit_service.record(
            session,
            event_type=event_type,
            entity_type=EntityType.OFFER,
            entity_id=offer.id,
            context=context,
            changes=changes,
            reason=reason,
            metadata=offer_metadata(offer),
            source_operation=source_operation,
        )
    return len(events)
