from __future__ import annotations

from app.core.config import settings


class AiokafkaAuditProducer:
    """Idempotent producer. acks=all, retries left at the client default."""

    def __init__(self, bootstrap_servers: str, client_id: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._producer = None

    async def start(self) -> None:
        if self._producer is not None:
            return
        from aiokafka import AIOKafkaProducer

        servers = [item.strip() for item in self._bootstrap_servers.split(",") if item.strip()]
        producer = AIOKafkaProducer(
            bootstrap_servers=servers,
            client_id=self._client_id,
            acks="all",
            enable_idempotence=True,
            request_timeout_ms=10_000,
            retry_backoff_ms=200,
        )
        try:
            await producer.start()
        except Exception:
            await producer.stop()
            raise
        self._producer = producer

    async def stop(self) -> None:
        producer = self._producer
        self._producer = None
        if producer is not None:
            await producer.stop()

    async def send(self, *, topic: str, key: str, value: bytes) -> None:
        if self._producer is None:
            await self.start()
        await self._producer.send_and_wait(topic, value=value, key=key.encode("utf-8"))


def build_audit_producer() -> AiokafkaAuditProducer:
    return AiokafkaAuditProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=settings.KAFKA_CLIENT_ID,
    )
