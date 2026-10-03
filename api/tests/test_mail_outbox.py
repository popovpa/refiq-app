import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.mail_events.crypto import MailEventCipher, decode_key
from app.mail_events.enqueue import enqueue_mail_command
from app.modules.audit.outbox.models import AuditOutboxEvent
from app.modules.audit.outbox.publisher import publish_once
from app.modules.auth.email_confirmation import EmailConfirmationService
from app.modules.auth.models import EmailConfirmationToken
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal
from tests.test_audit_outbox import RecordingProducer


@pytest.mark.asyncio
async def test_mail_event_rolls_back_with_confirmation_token(db: AsyncSession):
    user = User(email="rollback-mail@example.com", password_hash="hash", status="new")
    db.add(user)
    await db.flush()
    await EmailConfirmationService(db).issue(user)

    async with TestingSessionLocal() as other:
        hidden_user = await other.get(User, user.id)
        hidden_token = (
            await other.execute(
                select(EmailConfirmationToken).where(EmailConfirmationToken.user_id == user.id)
            )
        ).scalar_one_or_none()
        hidden_outbox = (
            await other.execute(
                select(AuditOutboxEvent).where(AuditOutboxEvent.aggregate_id == str(user.id))
            )
        ).scalar_one_or_none()
    assert hidden_user is None
    assert hidden_token is None
    assert hidden_outbox is None

    await db.rollback()

    async with TestingSessionLocal() as other:
        assert await other.get(User, user.id) is None
        assert (
            await other.execute(select(AuditOutboxEvent).where(AuditOutboxEvent.event_type == "MAIL_SEND_REQUESTED"))
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_publisher_sends_audit_and_mail_events_to_their_topics():
    cipher = MailEventCipher(
        decode_key(settings.MAIL_EVENT_ENCRYPTION_KEY),
        settings.MAIL_EVENT_ENCRYPTION_KEY_VERSION,
    )
    async with TestingSessionLocal() as session:
        user = User(email="publish-mail@example.com", password_hash="hash", status="active")
        session.add(user)
        await session.flush()
        await enqueue_mail_command(
            session,
            template_code="PASSWORD_RESET",
            template_version=1,
            idempotency_key=f"password-reset:{user.id}",
            user_id=user.id,
            recipient_email=user.email,
            variables={"resetUrl": "https://app.example/reset-password?token=secret-token", "ttlMinutes": 30},
            request_id="req-mail",
            correlation_id="req-mail",
        )
        session.add(
            AuditOutboxEvent(
                event_id="audit-evt-1",
                topic="audit-events",
                event_type="OFFER_CREATED",
                aggregate_type="OFFER",
                aggregate_id="900",
                partition_key="900",
                payload={
                    "schemaVersion": 1,
                    "eventId": "audit-evt-1",
                    "eventType": "OFFER_CREATED",
                    "occurredAt": "2026-10-04T00:00:00.000Z",
                    "entity": {"type": "OFFER", "id": "900"},
                    "requestId": "req-audit",
                    "correlationId": "req-audit",
                },
                created_at=datetime.now(timezone.utc),
                retry_count=0,
            )
        )
        await session.commit()
        user_id = user.id

    producer = RecordingProducer()
    published = await publish_once(TestingSessionLocal, producer, now=datetime.now(timezone.utc))
    assert published == 2
    topics = {topic for topic, _key, _value in producer.messages}
    assert topics == {"audit-events", "mail-events"}
    mail_messages = [item for item in producer.messages if item[0] == "mail-events"]
    assert len(mail_messages) == 1
    topic, key, raw = mail_messages[0]
    assert topic == "mail-events"
    assert key == str(user_id)
    body = json.loads(raw.decode())
    assert body["templateCode"] == "PASSWORD_RESET"
    assert "secret-token" not in raw.decode()
    assert "publish-mail@example.com" not in raw.decode()
    decoded = cipher.decrypt(
        event_id=body["eventId"],
        nonce=body["encryption"]["nonce"],
        ciphertext=body["encryptedPayload"],
        key_version=body["encryption"]["keyVersion"],
    )
    assert decoded["recipient"]["email"] == "publish-mail@example.com"
    assert "secret-token" in decoded["variables"]["resetUrl"]

    async with TestingSessionLocal() as session:
        rows = list((await session.execute(select(AuditOutboxEvent))).scalars().all())
    assert all(row.published_at is not None for row in rows)
