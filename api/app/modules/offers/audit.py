from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.audit.context import AuditContext
from app.modules.audit.diff import clone_value, field_changes, jsonable, values_equal
from app.modules.audit.events import EntityType, OfferEventType
from app.modules.audit.factory import audit_event_factory
from app.modules.audit.offer_state import (
    SNAPSHOT_FIELDS,
    commission_rules_state,
    kafka_changes,
    kafka_state,
)
from app.modules.audit.outbox.repository import outbox_repository
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

SPECIALIZED_EVENTS: tuple[tuple[str, frozenset[str]], ...] = (
    (OfferEventType.STATUS_CHANGED, frozenset({"status"})),
    (OfferEventType.HOLD_CHANGED, frozenset({"hold_period_days"})),
    (OfferEventType.TRAFFIC_POLICY_CHANGED, frozenset({"geo", "allowed_traffic", "forbidden_traffic"})),
    (OfferEventType.ACCESS_POLICY_CHANGED, frozenset({"access_policy", "visibility"})),
    (OfferEventType.PRODUCT_CHANGED, frozenset({"product_id"})),
)


def snapshot_offer(offer: Offer) -> dict[str, Any]:
    data = {field: clone_value(getattr(offer, field)) for field in SNAPSHOT_FIELDS}
    data["commission_rules"] = commission_rules_state(offer)
    return data


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
    await session.refresh(offer, attribute_names=["commission_rules"])
    await _enqueue_offer_event(
        session,
        offer,
        context,
        event_type=OfferEventType.CREATED,
        action="CREATE",
        before=None,
        after=kafka_state(offer),
        changes=None,
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
    await _enqueue_offer_mutations(
        session,
        offer,
        before,
        after,
        events,
        context,
        source_operation=source_operation,
        reason=reason,
    )
    return len(events)


def _commission_change(before: dict, after: dict) -> dict[str, Any] | None:
    old = before.get("commission_rules")
    new = after.get("commission_rules")
    if values_equal(old, new):
        return None
    return {"before": jsonable(old), "after": jsonable(new)}


def _with_commission(events: list[tuple[str, dict]], commission_change: dict[str, Any]) -> list[tuple[str, dict]]:
    attached = False
    prepared: list[tuple[str, dict]] = []
    for event_type, changes in events:
        if event_type == OfferEventType.UPDATED and not attached:
            copied = dict(changes)
            copied["commission_rules"] = commission_change
            prepared.append((event_type, copied))
            attached = True
        else:
            prepared.append((event_type, changes))
    if not attached:
        prepared.append((OfferEventType.UPDATED, {"commission_rules": commission_change}))
    return prepared


async def _enqueue_offer_mutations(
    session: AsyncSession,
    offer: Offer,
    before: dict,
    after: dict,
    events: list[tuple[str, dict]],
    context: AuditContext,
    *,
    source_operation: str,
    reason: str | None,
) -> None:
    if not settings.AUDIT_OUTBOX_ENABLED:
        return
    prepared = list(events)
    commission_change = _commission_change(before, after)
    if commission_change:
        prepared = _with_commission(prepared, commission_change)
    for event_type, changes in prepared:
        camel = kafka_changes(changes)
        if not camel:
            continue
        action = "STATUS_CHANGE" if event_type == OfferEventType.STATUS_CHANGED else "UPDATE"
        await _enqueue_offer_event(
            session,
            offer,
            context,
            event_type=event_type,
            action=action,
            before={key: value["before"] for key, value in camel.items()},
            after={key: value["after"] for key, value in camel.items()},
            changes=camel,
            source_operation=source_operation,
            reason=reason,
        )


async def _enqueue_offer_event(
    session: AsyncSession,
    offer: Offer,
    context: AuditContext,
    *,
    event_type: str,
    action: str,
    before: dict | None,
    after: dict | None,
    changes: dict | None,
    source_operation: str,
    reason: str | None = None,
) -> None:
    if not settings.AUDIT_OUTBOX_ENABLED:
        return
    if offer.id is None:
        raise RuntimeError("Offer id is required before writing the audit outbox")
    metadata = {"businessId": str(offer.business_id)}
    if offer.product_id is not None:
        metadata["productId"] = str(offer.product_id)
    if action == "CREATE":
        payload = audit_event_factory.offer_created(
            offer_id=offer.id,
            account_id=offer.business_id,
            context=context,
            after=after or {},
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
        )
    elif action == "STATUS_CHANGE":
        payload = audit_event_factory.offer_status_changed(
            offer_id=offer.id,
            account_id=offer.business_id,
            context=context,
            changes=changes or {},
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
        )
    else:
        payload = audit_event_factory.offer_updated(
            offer_id=offer.id,
            account_id=offer.business_id,
            context=context,
            changes=changes or {},
            event_type=event_type,
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
        )
    await outbox_repository.add(
        session,
        topic=settings.AUDIT_KAFKA_TOPIC,
        event_type=payload["eventType"],
        aggregate_type=EntityType.OFFER,
        aggregate_id=str(offer.id),
        partition_key=str(offer.id),
        payload=payload,
    )
