from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Protocol

import structlog

from app.core.config import settings
from app.modules.audit.outbox import metrics
from app.modules.audit.outbox.models import AuditOutboxEvent
from app.modules.audit.outbox.repository import as_utc, outbox_repository
from app.modules.audit.outbox.retry import retry_delay_seconds
from app.modules.audit.outbox.serialize import payload_bytes

logger = structlog.get_logger()

_ERROR_LIMIT = 500


class AuditEventProducer(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send(self, *, topic: str, key: str, value: bytes) -> None: ...


def _request_fields(payload: dict) -> tuple[str | None, str | None]:
    request_id = payload.get("requestId")
    correlation_id = payload.get("correlationId")
    return (
        request_id if isinstance(request_id, str) else None,
        correlation_id if isinstance(correlation_id, str) else None,
    )


def _log_fields(row: AuditOutboxEvent) -> dict:
    payload = row.payload if isinstance(row.payload, dict) else {}
    request_id, correlation_id = _request_fields(payload)
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id,
        "topic": row.topic,
        "retry_count": row.retry_count,
        "request_id": request_id,
        "correlation_id": correlation_id,
    }


def mark_published(row: AuditOutboxEvent, now: datetime) -> None:
    row.published_at = now
    row.last_error = None


def mark_failed(row: AuditOutboxEvent, exc: BaseException, now: datetime) -> None:
    row.published_at = None
    row.retry_count = int(row.retry_count or 0) + 1
    row.last_error = f"{type(exc).__name__}: {exc}"[:_ERROR_LIMIT]
    delay = retry_delay_seconds(row.retry_count, base_delay=settings.AUDIT_OUTBOX_RETRY_BASE_DELAY)
    row.next_retry_at = now + timedelta(seconds=delay)


async def _refresh_gauges(session, now: datetime) -> None:
    pending, oldest = await outbox_repository.pending_stats(session)
    metrics.set_gauge(metrics.PENDING, pending)
    if oldest is None:
        metrics.set_gauge(metrics.OLDEST_PENDING_AGE, 0.0)
    else:
        age = (now - as_utc(oldest)).total_seconds()
        metrics.set_gauge(metrics.OLDEST_PENDING_AGE, max(age, 0.0))


async def publish_pending(
    session,
    producer: AuditEventProducer,
    *,
    batch_size: int,
    now: datetime,
    publish_timeout: float,
) -> int:
    rows = await outbox_repository.claim_pending(session, batch_size=batch_size, now=now)
    published = 0
    for row in rows:
        started = asyncio.get_running_loop().time()
        try:
            body = payload_bytes(row.payload if isinstance(row.payload, dict) else {})
            await asyncio.wait_for(
                producer.send(topic=row.topic, key=row.partition_key, value=body),
                timeout=publish_timeout,
            )
        except Exception as exc:
            mark_failed(row, exc, now)
            metrics.inc(metrics.ERRORS)
            metrics.inc(metrics.RETRIES)
            log = _log_fields(row)
            logger.warning("audit_outbox_publish_failed", error=row.last_error, **log)
            if row.retry_count == settings.AUDIT_OUTBOX_MAX_RETRIES:
                logger.error("audit_outbox_retry_cap_exceeded", **log)
            continue
        mark_published(row, now)
        published += 1
        metrics.inc(metrics.PUBLISHED)
        metrics.set_gauge(metrics.LATENCY, asyncio.get_running_loop().time() - started)
        logger.info("audit_outbox_published", **_log_fields(row))
    return published


async def publish_once(
    session_factory,
    producer: AuditEventProducer,
    *,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(timezone.utc)
    async with session_factory() as session:
        try:
            published = await publish_pending(
                session,
                producer,
                batch_size=settings.AUDIT_OUTBOX_BATCH_SIZE,
                now=current,
                publish_timeout=settings.AUDIT_OUTBOX_PUBLISH_TIMEOUT,
            )
            await session.flush()
            await _refresh_gauges(session, current)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    retention = settings.AUDIT_OUTBOX_RETENTION_SECONDS
    if retention > 0:
        cutoff = current - timedelta(seconds=retention)
        async with session_factory() as session:
            try:
                await outbox_repository.delete_published_before(session, cutoff)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("audit_outbox_cleanup_failed")
    return published
