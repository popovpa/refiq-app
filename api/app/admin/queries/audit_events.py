from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import encode_cursor, iso, keyset_before
from app.modules.system.models import AuditLog


def serialize_audit_log(event: AuditLog) -> dict:
    return {
        "id": event.id,
        "event_id": event.event_id,
        "schema_version": event.schema_version,
        "created_at": iso(event.occurred_at),
        "occurred_at": iso(event.occurred_at),
        "ingested_at": iso(event.ingested_at),
        "event_type": event.event_type,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "account_id": event.account_id,
        "request_id": event.request_id,
        "correlation_id": event.correlation_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "changes": event.changed_fields,
        "before": event.before_data,
        "after": event.after_data,
        "metadata": event.metadata_,
    }


async def list_audit_events(
    db: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 50,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_type: str | None = None,
    account_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    stmt = (
        select(AuditLog)
        .where(keyset_before(AuditLog.occurred_at, AuditLog.id, cursor))
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(limit + 1)
    )
    if date_from is not None:
        stmt = stmt.where(AuditLog.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.occurred_at <= date_to)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_type:
        stmt = stmt.where(AuditLog.actor_type == actor_type)
    if account_id:
        stmt = stmt.where(
            or_(
                AuditLog.account_id == account_id,
                AuditLog.metadata_["accountId"].as_string() == account_id,
            )
        )
    if request_id:
        stmt = stmt.where(AuditLog.request_id == request_id)

    rows = (await db.execute(stmt)).scalars().all()
    sliced = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = encode_cursor(sliced[-1].occurred_at, sliced[-1].id) if has_more and sliced else None
    return {
        "items": [serialize_audit_log(event) for event in sliced],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
