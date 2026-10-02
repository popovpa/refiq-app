import asyncio
import json
import socket
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.audit.context import AuditContext
from app.modules.audit.events import ActorType, OfferEventType
from app.modules.audit.offer_state import kafka_changes
from app.modules.audit.outbox import metrics
from app.modules.audit.outbox.models import AuditOutboxEvent
from app.modules.audit.outbox.publisher import publish_once
from app.modules.audit.outbox.repository import claim_statement, outbox_repository
from app.modules.audit.outbox.retry import retry_delay_seconds
from app.modules.offers.audit import record_offer_created, record_offer_mutations, snapshot_offer
from app.modules.offers.models import Offer
from app.workers.outbox_publisher import OutboxPublisherWorker
from tests.conftest import TestingSessionLocal
from tests.helpers import offer_payload, register_business


class RecordingProducer:
    def __init__(
        self,
        *,
        fail: BaseException | None = None,
        fail_sends: int | None = None,
        keep_failed: bool = False,
    ) -> None:
        self.messages: list[tuple[str, str, bytes]] = []
        self.fail = fail
        self.fail_sends = fail_sends
        self.keep_failed = keep_failed
        self.started = 0
        self.stopped = 0

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

    async def send(self, *, topic: str, key: str, value: bytes) -> None:
        should_fail = False
        if self.fail is not None and self.fail_sends is None:
            should_fail = True
        elif self.fail is not None and self.fail_sends:
            self.fail_sends -= 1
            should_fail = True
        if should_fail:
            if self.keep_failed:
                self.messages.append((topic, key, value))
            raise self.fail
        self.messages.append((topic, key, value))


def _decode(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))


async def _rows(offer_id: int) -> list[AuditOutboxEvent]:
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(AuditOutboxEvent)
            .where(AuditOutboxEvent.aggregate_id == str(offer_id))
            .order_by(AuditOutboxEvent.id.asc())
        )
        return list(result.scalars().all())


async def _create_offer(client: AsyncClient, **overrides) -> dict:
    await register_business(client, overrides.pop("email", "outbox-offer@example.com"))
    created = await client.post("/api/v1/business/offers", json=offer_payload(**overrides))
    assert created.status_code == 200, created.text
    return created.json()


def _context(**overrides) -> AuditContext:
    data = dict(
        actor_type=ActorType.USER,
        source_service="api",
        user_id=11,
        business_id=22,
        request_id="req-outbox",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    data.update(overrides)
    return AuditContext(**data)


@pytest.fixture(autouse=True)
def _reset_outbox_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_retry_schedule_is_bounded():
    assert retry_delay_seconds(1, base_delay=1) == 1
    assert retry_delay_seconds(2, base_delay=1) == 5
    assert retry_delay_seconds(3, base_delay=1) == 15
    assert retry_delay_seconds(4, base_delay=1) == 30
    assert retry_delay_seconds(5, base_delay=1) == 60
    assert retry_delay_seconds(9, base_delay=1) == 60
    assert retry_delay_seconds(2, base_delay=2) == 10


def test_claim_uses_skip_locked_on_postgresql():
    statement = claim_statement(datetime.now(timezone.utc), 100, lock=True)
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "SKIP LOCKED" in sql
    assert "outbox_event" in sql
    assert "published_at IS NULL" in sql


def test_kafka_changes_allowlist_drops_secrets():
    converted = kafka_changes(
        {
            "hold_period_days": {"before": 7, "after": 14},
            "password": {"before": "old", "after": "new"},
            "api_key": {"before": "k", "after": "k2"},
            "refresh_token": {"before": "r", "after": "r2"},
        }
    )
    assert converted == {"holdPeriodDays": {"before": 7, "after": 14}}


@pytest.mark.asyncio
async def test_offer_and_outbox_commit_together(db: AsyncSession):
    offer = Offer(business_id=22, name="Atomic offer", status="draft", hold_period_days=7)
    db.add(offer)
    await db.flush()
    await record_offer_created(db, offer, _context())

    async with TestingSessionLocal() as other:
        hidden_offer = await other.get(Offer, offer.id)
        hidden_outbox = (
            await other.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.aggregate_id == str(offer.id)))
        ).scalar_one_or_none()
        assert hidden_offer is None
        assert hidden_outbox is None

    await db.commit()

    async with TestingSessionLocal() as other:
        stored = await other.get(Offer, offer.id)
        outbox = (
            await other.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.aggregate_id == str(offer.id)))
        ).scalar_one()
        assert stored.name == "Atomic offer"
        assert outbox.event_type == OfferEventType.CREATED
        assert outbox.published_at is None
        assert outbox.payload["eventId"] == outbox.event_id


@pytest.mark.asyncio
async def test_outbox_insert_failure_rolls_back_offer(db: AsyncSession, monkeypatch):
    offer = Offer(business_id=22, name="Rollback offer", status="draft")
    db.add(offer)
    await db.flush()
    await db.commit()
    offer_id = offer.id

    async def boom(*_args, **_kwargs):
        raise RuntimeError("outbox insert failed")

    monkeypatch.setattr("app.modules.offers.audit.outbox_repository.add", boom)
    offer = await db.get(Offer, offer_id)
    before = snapshot_offer(offer)
    offer.status = "active"
    with pytest.raises(RuntimeError, match="outbox insert failed"):
        await record_offer_mutations(db, offer, before, snapshot_offer(offer), _context())
    await db.rollback()

    async with TestingSessionLocal() as other:
        stored = await other.get(Offer, offer_id)
        assert stored.status == "draft"
        status_rows = (
            await other.execute(
                select(AuditOutboxEvent).where(
                    AuditOutboxEvent.aggregate_id == str(offer_id),
                    AuditOutboxEvent.event_type == OfferEventType.STATUS_CHANGED,
                )
            )
        ).scalars().all()
        assert status_rows == []


@pytest.mark.asyncio
async def test_create_offer_writes_one_created_event(client: AsyncClient):
    body = await _create_offer(client, name="Created offer", hold_period_days=7, status="draft")
    rows = await _rows(body["id"])
    assert len(rows) == 1
    row = rows[0]
    payload = row.payload
    assert row.topic == "audit-events"
    assert row.partition_key == str(body["id"])
    assert row.aggregate_type == "OFFER"
    assert row.published_at is None
    assert payload["schemaVersion"] == 1
    assert payload["eventType"] == "OFFER_CREATED"
    assert payload["action"] == "CREATE"
    assert payload["before"] is None
    assert payload["changes"] is None
    assert payload["after"]["name"] == "Created offer"
    assert payload["after"]["status"] == "draft"
    assert payload["after"]["holdPeriodDays"] == 7
    assert payload["after"]["commissionRules"][0]["type"] == "percent"
    assert payload["entity"] == {"type": "OFFER", "id": str(body["id"])}
    assert payload["actor"]["type"] == "USER"
    assert payload["actor"]["id"]
    assert payload["accountId"]
    assert payload["requestId"]
    assert payload["correlationId"] == payload["requestId"]
    assert "password" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_update_writes_before_after_and_changes(client: AsyncClient):
    body = await _create_offer(client, email="outbox-update@example.com", hold_period_days=7, name="Offer A")
    patched = await client.patch(f"/api/v1/business/offers/{body['id']}", json={"hold_period_days": 14})
    assert patched.status_code == 200, patched.text
    rows = await _rows(body["id"])
    assert [row.event_type for row in rows] == [OfferEventType.CREATED, OfferEventType.HOLD_CHANGED]
    updated = rows[-1].payload
    assert updated["action"] == "UPDATE"
    assert updated["changes"]["holdPeriodDays"] == {"before": 7, "after": 14}
    assert updated["before"] == {"holdPeriodDays": 7}
    assert updated["after"] == {"holdPeriodDays": 14}
    assert rows[0].partition_key == rows[1].partition_key == str(body["id"])


@pytest.mark.asyncio
async def test_status_change_is_its_own_event(client: AsyncClient):
    body = await _create_offer(client, email="outbox-status@example.com", status="draft")
    patched = await client.patch(f"/api/v1/business/offers/{body['id']}", json={"status": "active"})
    assert patched.status_code == 200, patched.text
    status_row = (await _rows(body["id"]))[-1]
    assert status_row.event_type == OfferEventType.STATUS_CHANGED
    assert status_row.payload["action"] == "STATUS_CHANGE"
    assert status_row.payload["changes"]["status"] == {"before": "draft", "after": "active"}


@pytest.mark.asyncio
async def test_noop_update_does_not_write_outbox(client: AsyncClient):
    body = await _create_offer(client, email="outbox-noop@example.com", status="draft", name="Test offer")
    before = len(await _rows(body["id"]))
    patched = await client.patch(
        f"/api/v1/business/offers/{body['id']}",
        json={"status": "draft", "name": "Test offer"},
    )
    assert patched.status_code == 200, patched.text
    assert len(await _rows(body["id"])) == before


@pytest.mark.asyncio
async def test_disabled_audit_does_not_block_offer_create(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_OUTBOX_ENABLED", False)
    body = await _create_offer(client, email="outbox-disabled@example.com", name="Still created")
    assert body["name"] == "Still created"
    assert await _rows(body["id"]) == []


@pytest.mark.asyncio
async def test_http_create_does_not_call_kafka(client: AsyncClient, monkeypatch):
    async def fail_send(self, **_kwargs):
        raise AssertionError("Kafka was called from the request")

    monkeypatch.setattr("app.kafka.producer.AiokafkaAuditProducer.send", fail_send)
    body = await _create_offer(client, email="outbox-kafka-down@example.com")
    rows = await _rows(body["id"])
    assert len(rows) == 1
    assert rows[0].published_at is None


@pytest.mark.asyncio
async def test_publisher_retries_then_publishes_same_event_id():
    metrics.reset()
    offer_id = "501"
    async with TestingSessionLocal() as session:
        payload = {
            "schemaVersion": 1,
            "eventId": "evt-stable",
            "eventType": "OFFER_CREATED",
            "occurredAt": "2026-10-03T12:30:15.123Z",
            "actor": {"type": "USER", "id": "11"},
            "entity": {"type": "OFFER", "id": offer_id},
            "action": "CREATE",
            "accountId": "22",
            "requestId": "req-1",
            "correlationId": "req-1",
            "before": None,
            "after": {"name": "A"},
            "changes": None,
            "metadata": {},
        }
        await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id=offer_id,
            partition_key=offer_id,
            payload=payload,
        )
        await session.commit()

    failing = RecordingProducer(fail=ConnectionError("kafka unavailable"), fail_sends=1)
    now = datetime.now(timezone.utc)
    await publish_once(TestingSessionLocal, failing, now=now)
    assert failing.messages == []

    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == "evt-stable"))
        ).scalar_one()
        assert row.published_at is None
        assert row.retry_count == 1
        assert "kafka unavailable" in row.last_error
        assert row.next_retry_at is not None
        retry_at = row.next_retry_at

    too_soon = RecordingProducer()
    await publish_once(TestingSessionLocal, too_soon, now=now)
    assert too_soon.messages == []

    recovered = RecordingProducer()
    await publish_once(TestingSessionLocal, recovered, now=retry_at + timedelta(seconds=1))
    assert len(recovered.messages) == 1
    topic, key, raw = recovered.messages[0]
    body = _decode(raw)
    assert topic == "audit-events"
    assert key == offer_id
    assert body["eventId"] == "evt-stable"
    assert body["entity"]["id"] == offer_id

    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == "evt-stable"))
        ).scalar_one()
        assert row.published_at is not None
        assert row.event_id == "evt-stable"

    snapshot = metrics.snapshot()
    assert snapshot["outbox.published"] >= 1
    assert snapshot["outbox.publish.errors"] >= 1
    assert snapshot["outbox.retries"] >= 1
    assert "outbox.publish.latency" in snapshot
    assert "outbox.pending" in snapshot
    assert "outbox.oldest.pending.age" in snapshot


@pytest.mark.asyncio
async def test_republish_after_lost_ack_keeps_event_id():
    offer_id = "502"
    async with TestingSessionLocal() as session:
        payload = {
            "schemaVersion": 1,
            "eventId": "evt-replay",
            "eventType": "OFFER_UPDATED",
            "occurredAt": "2026-10-03T12:30:15.123Z",
            "actor": {"type": "SYSTEM"},
            "entity": {"type": "OFFER", "id": offer_id},
            "action": "UPDATE",
            "changes": {"name": {"before": "A", "after": "B"}},
            "before": {"name": "A"},
            "after": {"name": "B"},
            "metadata": {},
        }
        await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_UPDATED",
            aggregate_type="OFFER",
            aggregate_id=offer_id,
            partition_key=offer_id,
            payload=payload,
        )
        await session.commit()

    lost_ack = RecordingProducer(
        fail=ConnectionError("ack lost before published_at"),
        fail_sends=1,
        keep_failed=True,
    )
    now = datetime.now(timezone.utc)
    await publish_once(TestingSessionLocal, lost_ack, now=now)
    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == "evt-replay"))
        ).scalar_one()
        assert row.published_at is None
        due = row.next_retry_at

    recovered = RecordingProducer()
    await publish_once(TestingSessionLocal, recovered, now=due + timedelta(seconds=1))
    sent = [_decode(raw)["eventId"] for _topic, _key, raw in lost_ack.messages + recovered.messages]
    assert sent == ["evt-replay", "evt-replay"]
    assert [key for _topic, key, _raw in lost_ack.messages + recovered.messages] == [offer_id, offer_id]


@pytest.mark.asyncio
async def test_older_unpublished_event_blocks_a_newer_one_for_the_same_offer():
    created = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        first = {
            "schemaVersion": 1,
            "eventId": "evt-first",
            "eventType": "OFFER_CREATED",
            "occurredAt": "2026-10-03T12:30:15.123Z",
            "actor": {"type": "USER", "id": "1"},
            "entity": {"type": "OFFER", "id": "77"},
            "action": "CREATE",
            "metadata": {},
        }
        second = {
            **first,
            "eventId": "evt-second",
            "eventType": "OFFER_UPDATED",
            "action": "UPDATE",
        }
        await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id="77",
            partition_key="77",
            payload=first,
        )
        await session.commit()
    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == "evt-first"))
        ).scalar_one()
        row.next_retry_at = created + timedelta(hours=1)
        await session.commit()
    async with TestingSessionLocal() as session:
        await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_UPDATED",
            aggregate_type="OFFER",
            aggregate_id="77",
            partition_key="77",
            payload=second,
        )
        await session.commit()

    producer = RecordingProducer()
    await publish_once(TestingSessionLocal, producer, now=created)
    assert producer.messages == []

    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == "evt-first"))
        ).scalar_one()
        row.next_retry_at = None
        await session.commit()

    await publish_once(TestingSessionLocal, producer, now=created)
    assert [_decode(raw)["eventId"] for _topic, _key, raw in producer.messages] == ["evt-first"]
    await publish_once(TestingSessionLocal, producer, now=created)
    assert [_decode(raw)["eventId"] for _topic, _key, raw in producer.messages] == ["evt-first", "evt-second"]
    assert {key for _topic, key, _raw in producer.messages} == {"77"}


@pytest.mark.asyncio
async def test_admin_status_change_uses_admin_actor(db: AsyncSession):
    offer = Offer(business_id=9, name="Admin offer", status="active")
    db.add(offer)
    await db.flush()
    before = snapshot_offer(offer)
    offer.status = "paused"
    await record_offer_mutations(
        db,
        offer,
        before,
        snapshot_offer(offer),
        _context(actor_type=ActorType.ADMIN, source_service="admin", user_id=None, admin_id=4, business_id=None),
        source_operation="admin.offers.pause",
        reason="policy",
    )
    await db.commit()
    rows = await _rows(offer.id)
    assert rows[-1].event_type == OfferEventType.STATUS_CHANGED
    assert rows[-1].payload["actor"] == {"type": "ADMIN", "id": "4"}
    assert rows[-1].payload["accountId"] == "9"
    assert rows[-1].payload["metadata"]["reason"] == "policy"


@pytest.mark.asyncio
async def test_cleanup_removes_only_expired_published_rows():
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        old_payload = _payload("evt-old", "81")
        fresh_payload = _payload("evt-fresh", "82")
        pending_payload = _payload("evt-pending", "83")
        old = await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id="81",
            partition_key="81",
            payload=old_payload,
        )
        fresh = await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id="82",
            partition_key="82",
            payload=fresh_payload,
        )
        await outbox_repository.add(
            session,
            topic="audit-events",
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id="83",
            partition_key="83",
            payload=pending_payload,
        )
        old.published_at = now - timedelta(days=10)
        fresh.published_at = now
        await session.commit()

    async with TestingSessionLocal() as session:
        deleted = await outbox_repository.delete_published_before(session, now - timedelta(days=7))
        await session.commit()
        assert deleted == 1
        remaining = set((await session.execute(select(AuditOutboxEvent.event_id))).scalars().all())
        assert remaining == {"evt-fresh", "evt-pending"}


@pytest.mark.asyncio
async def test_publisher_shutdown_finishes_current_cycle_and_stops():
    calls = {"n": 0}
    started = asyncio.Event()

    class Producer(RecordingProducer):
        async def start(self) -> None:
            await super().start()
            calls["n"] += 1
            started.set()

    producer = Producer()
    worker = OutboxPublisherWorker(
        producer,
        session_factory=TestingSessionLocal,
        poll_interval=30,
        shutdown_timeout=2,
    )
    worker.start()
    await asyncio.wait_for(started.wait(), timeout=1)
    await worker.shutdown()
    assert calls["n"] == 1
    assert producer.stopped == 1


@pytest.mark.asyncio
async def test_producer_requires_acks_all_and_idempotence(monkeypatch):
    captured: dict = {}

    class FakeProducer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def start(self):
            return None

        async def stop(self):
            return None

    import aiokafka

    monkeypatch.setattr(aiokafka, "AIOKafkaProducer", FakeProducer)
    from app.kafka.producer import AiokafkaAuditProducer

    producer = AiokafkaAuditProducer("localhost:9092", "refiq-api")
    await producer.start()
    assert captured["acks"] == "all"
    assert captured["enable_idempotence"] is True
    assert captured.get("retries", 1) != 0


def _payload(event_id: str, offer_id: str) -> dict:
    return {
        "schemaVersion": 1,
        "eventId": event_id,
        "eventType": "OFFER_CREATED",
        "occurredAt": "2026-10-03T12:30:15.123Z",
        "actor": {"type": "USER", "id": "1"},
        "entity": {"type": "OFFER", "id": offer_id},
        "action": "CREATE",
        "metadata": {},
    }


def _kafka_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


@pytest.mark.asyncio
async def test_live_kafka_round_trip_when_broker_is_up():
    server = settings.KAFKA_BOOTSTRAP_SERVERS.split(",")[0].strip()
    if ":" not in server:
        pytest.skip("Kafka bootstrap server is not configured")
    host, port_text = server.rsplit(":", 1)
    if not _kafka_reachable(host, int(port_text)):
        pytest.skip("Kafka broker is not reachable")

    from aiokafka import AIOKafkaConsumer

    from app.kafka.producer import AiokafkaAuditProducer

    event_id = "evt-live-outbox"
    offer_id = "900"
    async with TestingSessionLocal() as session:
        await outbox_repository.add(
            session,
            topic=settings.AUDIT_KAFKA_TOPIC,
            event_type="OFFER_CREATED",
            aggregate_type="OFFER",
            aggregate_id=offer_id,
            partition_key=offer_id,
            payload=_payload(event_id, offer_id),
        )
        await session.commit()

    producer = AiokafkaAuditProducer(settings.KAFKA_BOOTSTRAP_SERVERS, "refiq-api-test")
    consumer = AIOKafkaConsumer(
        settings.AUDIT_KAFKA_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"refiq-api-audit-test-{event_id}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        await publish_once(TestingSessionLocal, producer)
        found = None
        deadline = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < deadline and found is None:
            batches = await consumer.getmany(timeout_ms=500, max_records=20)
            for messages in batches.values():
                for message in messages:
                    if message.key == offer_id.encode("utf-8"):
                        body = json.loads(message.value.decode("utf-8"))
                        if body.get("eventId") == event_id:
                            found = body
                            break
        assert found is not None
        assert found["schemaVersion"] == 1
        assert found["entity"]["id"] == offer_id
    finally:
        await consumer.stop()
        await producer.stop()

    async with TestingSessionLocal() as session:
        row = (
            await session.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_id == event_id))
        ).scalar_one()
        assert row.published_at is not None
