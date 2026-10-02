from __future__ import annotations

import asyncio

import structlog

from app.core.config import settings
from app.core.database import async_session_factory
from app.kafka.producer import build_audit_producer
from app.modules.audit.outbox.publisher import AuditEventProducer, publish_once

logger = structlog.get_logger()


class OutboxPublisherWorker:
    def __init__(
        self,
        producer: AuditEventProducer,
        *,
        session_factory=async_session_factory,
        poll_interval: float | None = None,
        shutdown_timeout: float | None = None,
    ) -> None:
        self._producer = producer
        self._session_factory = session_factory
        self._poll_interval = settings.AUDIT_OUTBOX_POLL_INTERVAL if poll_interval is None else poll_interval
        self._shutdown_timeout = (
            settings.AUDIT_OUTBOX_SHUTDOWN_TIMEOUT if shutdown_timeout is None else shutdown_timeout
        )
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await self._producer.start()
                    await publish_once(self._session_factory, self._producer)
                except Exception:
                    logger.exception("audit_outbox_cycle_failed")
                delay = self._poll_interval if self._poll_interval > 0 else 0.05
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
        finally:
            await self._producer.stop()

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task is None:
            await self._producer.stop()
            return
        try:
            await asyncio.wait_for(self._task, timeout=self._shutdown_timeout)
        except TimeoutError:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


def start_outbox_publisher() -> OutboxPublisherWorker | None:
    if not settings.AUDIT_OUTBOX_ENABLED:
        logger.info("audit_outbox_disabled")
        return None
    from app.modules.ai.jobs import has_test_job_runner

    if has_test_job_runner():
        return None
    worker = OutboxPublisherWorker(build_audit_producer())
    worker.start()
    return worker


async def shutdown_outbox_publisher(worker: OutboxPublisherWorker | None) -> None:
    if worker is not None:
        await worker.shutdown()
