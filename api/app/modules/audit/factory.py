from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.modules.audit.context import AuditContext
from app.modules.audit.events import EntityType
from app.modules.audit.sanitizer import sanitize_payload

SCHEMA_VERSION = 1
AUDIT_ACTOR_TYPES = frozenset({"USER", "ADMIN", "SYSTEM", "SERVICE", "API_CLIENT"})
AUDIT_ACTIONS = frozenset(
    {
        "CREATE",
        "UPDATE",
        "DELETE",
        "STATUS_CHANGE",
        "APPROVE",
        "REJECT",
        "ENABLE",
        "DISABLE",
        "PERMISSION_CHANGE",
        "PAYMENT_ACTION",
        "SYSTEM_ACTION",
    }
)

_SHORT_TEXT = 128
_USER_AGENT = 2000


def utc_timestamp(value: datetime | None = None) -> str:
    current = (value or datetime.now(timezone.utc)).astimezone(timezone.utc)
    millis = current.microsecond // 1000
    return current.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"


def new_event_id() -> str:
    return str(uuid.uuid4())


def _clip(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _actor(context: AuditContext) -> dict[str, str]:
    if context.actor_type not in AUDIT_ACTOR_TYPES:
        raise ValueError(f"Unsupported audit actor type: {context.actor_type}")
    actor = {"type": context.actor_type}
    actor_id = _actor_id(context)
    if actor_id:
        actor["id"] = actor_id
    return actor


def _actor_id(context: AuditContext) -> str | None:
    if context.actor_type == "ADMIN":
        return _clip(context.admin_id, _SHORT_TEXT)
    if context.actor_type in {"USER", "API_CLIENT"}:
        return _clip(context.user_id, _SHORT_TEXT)
    return None


class AuditEventFactory:
    """Builds the schemaVersion=1 AuditEvent document stored in the outbox."""

    def offer_created(
        self,
        *,
        offer_id: int,
        account_id: int | None,
        context: AuditContext,
        after: dict,
        source_operation: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        return self._build(
            event_type="OFFER_CREATED",
            action="CREATE",
            offer_id=offer_id,
            account_id=account_id,
            context=context,
            before=None,
            after=after,
            changes=None,
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    def offer_updated(
        self,
        *,
        offer_id: int,
        account_id: int | None,
        context: AuditContext,
        changes: dict,
        event_type: str = "OFFER_UPDATED",
        source_operation: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        before, after = _sides(changes)
        return self._build(
            event_type=event_type,
            action="UPDATE",
            offer_id=offer_id,
            account_id=account_id,
            context=context,
            before=before,
            after=after,
            changes=changes,
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    def offer_status_changed(
        self,
        *,
        offer_id: int,
        account_id: int | None,
        context: AuditContext,
        changes: dict,
        source_operation: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> dict[str, Any]:
        before, after = _sides(changes)
        return self._build(
            event_type="OFFER_STATUS_CHANGED",
            action="STATUS_CHANGE",
            offer_id=offer_id,
            account_id=account_id,
            context=context,
            before=before,
            after=after,
            changes=changes,
            source_operation=source_operation,
            reason=reason,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    def _build(
        self,
        *,
        event_type: str,
        action: str,
        offer_id: int,
        account_id: int | None,
        context: AuditContext,
        before: dict | None,
        after: dict | None,
        changes: dict | None,
        source_operation: str | None,
        reason: str | None,
        metadata: dict | None,
        occurred_at: datetime | None,
    ) -> dict[str, Any]:
        if action not in AUDIT_ACTIONS:
            raise ValueError(f"Unsupported audit action: {action}")
        entity_id = _clip(offer_id, _SHORT_TEXT)
        if not entity_id:
            raise ValueError("Offer id is required for an audit event")
        event: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "eventId": new_event_id(),
            "eventType": _clip(event_type, _SHORT_TEXT),
            "occurredAt": utc_timestamp(occurred_at),
            "actor": _actor(context),
            "entity": {"type": EntityType.OFFER, "id": entity_id},
            "action": action,
            "changes": sanitize_payload(changes) if changes else None,
            "before": sanitize_payload(before) if before else None,
            "after": sanitize_payload(after) if after else None,
            "metadata": _metadata(context, source_operation, reason, metadata),
        }
        account = _clip(account_id if account_id is not None else context.account_id, _SHORT_TEXT)
        if account:
            event["accountId"] = account
        request_id = _clip(context.request_id, _SHORT_TEXT)
        if request_id:
            event["requestId"] = request_id
        correlation_id = _clip(context.correlation_id or context.request_id, _SHORT_TEXT)
        if correlation_id:
            event["correlationId"] = correlation_id
        ip_address = _clip(context.ip_address, 45)
        if ip_address:
            event["ipAddress"] = ip_address
        user_agent = _clip(context.user_agent, _USER_AGENT)
        if user_agent:
            event["userAgent"] = user_agent
        return event


def _sides(changes: dict) -> tuple[dict, dict]:
    before = {key: value.get("before") for key, value in changes.items() if isinstance(value, dict)}
    after = {key: value.get("after") for key, value in changes.items() if isinstance(value, dict)}
    return before, after


def _metadata(
    context: AuditContext,
    source_operation: str | None,
    reason: str | None,
    extra: dict | None,
) -> dict:
    metadata: dict[str, Any] = {"sourceService": context.source_service}
    if source_operation:
        metadata["sourceOperation"] = source_operation
    if reason:
        metadata["reason"] = reason
    if extra:
        metadata.update(extra)
    return sanitize_payload(metadata) or {}


audit_event_factory = AuditEventFactory()
