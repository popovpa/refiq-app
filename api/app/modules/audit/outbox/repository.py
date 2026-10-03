from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.audit.outbox.models import AuditOutboxEvent


def claim_statement(now: datetime, batch_size: int, *, lock: bool = True):
    """Oldest due row per partition key.

    A newer event for the same topic and partition key stays unpublished until the older one is published.
    On PostgreSQL the selected rows are locked with FOR UPDATE SKIP LOCKED so two API
    replicas cannot publish the same row at the same time.
    """
    older = aliased(AuditOutboxEvent)
    older_unpublished = exists(
        select(older.id).where(
            older.published_at.is_(None),
            older.topic == AuditOutboxEvent.topic,
            older.partition_key == AuditOutboxEvent.partition_key,
            older.id < AuditOutboxEvent.id,
        )
    )
    stmt = (
        select(AuditOutboxEvent)
        .where(AuditOutboxEvent.published_at.is_(None))
        .where(or_(AuditOutboxEvent.next_retry_at.is_(None), AuditOutboxEvent.next_retry_at <= now))
        .where(~older_unpublished)
        .order_by(AuditOutboxEvent.created_at.asc(), AuditOutboxEvent.id.asc())
        .limit(batch_size)
    )
    if lock:
        stmt = stmt.with_for_update(skip_locked=True, of=AuditOutboxEvent)
    return stmt


class OutboxRepository:
    async def add(
        self,
        session: AsyncSession,
        *,
        topic: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        partition_key: str,
        payload: dict,
    ) -> AuditOutboxEvent:
        event_id = str(payload.get("eventId") or "")
        if not event_id:
            raise ValueError("Audit payload is missing eventId")
        if payload.get("eventType") != event_type:
            raise ValueError("Outbox event_type does not match payload")
        # Audit documents carry entity.id. Other transport envelopes, such as mail,
        # are keyed by aggregate_id and do not have an audit entity.
        if "entity" in payload:
            entity = payload.get("entity") or {}
            if str(entity.get("id")) != aggregate_id or partition_key != aggregate_id:
                raise ValueError("Kafka key, aggregate_id and entity.id must match")
        elif partition_key != aggregate_id:
            raise ValueError("Kafka key and aggregate_id must match")
        row = AuditOutboxEvent(
            event_id=event_id,
            topic=topic,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            partition_key=partition_key,
            payload=payload,
            created_at=datetime.now(timezone.utc),
            retry_count=0,
        )
        session.add(row)
        await session.flush()
        return row

    async def claim_pending(
        self,
        session: AsyncSession,
        *,
        batch_size: int,
        now: datetime,
    ) -> list[AuditOutboxEvent]:
        dialect = session.bind.dialect.name if session.bind is not None else "postgresql"
        stmt = claim_statement(now, batch_size, lock=dialect == "postgresql")
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def pending_stats(self, session: AsyncSession) -> tuple[int, datetime | None]:
        pending = await session.scalar(
            select(func.count())
            .select_from(AuditOutboxEvent)
            .where(AuditOutboxEvent.published_at.is_(None))
        )
        oldest = await session.scalar(
            select(func.min(AuditOutboxEvent.created_at)).where(AuditOutboxEvent.published_at.is_(None))
        )
        return int(pending or 0), oldest

    async def delete_published_before(self, session: AsyncSession, cutoff: datetime) -> int:
        result = await session.execute(
            delete(AuditOutboxEvent).where(
                AuditOutboxEvent.published_at.is_not(None),
                AuditOutboxEvent.published_at < cutoff,
            )
        )
        return int(result.rowcount or 0)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def retention_cutoff(now: datetime, retention_seconds: int) -> datetime | None:
    if retention_seconds <= 0:
        return None
    return now - timedelta(seconds=retention_seconds)


outbox_repository = OutboxRepository()
