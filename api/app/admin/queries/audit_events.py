from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import encode_cursor, iso, keyset_before
from app.modules.audit.models import AuditEvent


def serialize_audit_event(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "schema_version": event.schema_version,
        "created_at": iso(event.created_at),
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "actor_type": event.actor_type,
        "actor_user_id": event.actor_user_id,
        "actor_admin_id": event.actor_admin_id,
        "actor_business_id": event.actor_business_id,
        "actor_partner_id": event.actor_partner_id,
        "source_service": event.source_service,
        "source_operation": event.source_operation,
        "request_id": event.request_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "reason": event.reason,
        "changes": event.changes,
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
    entity_id: int | None = None,
    actor_type: str | None = None,
    business_id: int | None = None,
    request_id: str | None = None,
) -> dict:
    stmt = (
        select(AuditEvent)
        .where(keyset_before(AuditEvent.created_at, AuditEvent.id, cursor))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit + 1)
    )
    if date_from is not None:
        stmt = stmt.where(AuditEvent.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditEvent.created_at <= date_to)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if actor_type:
        stmt = stmt.where(AuditEvent.actor_type == actor_type)
    if business_id is not None:
        stmt = stmt.where(
            or_(
                AuditEvent.actor_business_id == business_id,
                AuditEvent.metadata_["business_id"].as_string() == str(business_id),
            )
        )
    if request_id:
        stmt = stmt.where(AuditEvent.request_id == request_id)

    rows = (await db.execute(stmt)).scalars().all()
    sliced = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = encode_cursor(sliced[-1].created_at, sliced[-1].id) if has_more and sliced else None
    return {
        "items": [serialize_audit_event(event) for event in sliced],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
