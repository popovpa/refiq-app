from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.mail_events.crypto import MailEventCipher, decode_key
from app.modules.audit.outbox.repository import outbox_repository

EVENT_TYPE = "MAIL_SEND_REQUESTED"
SCHEMA_VERSION = 1


def validate_mail_event_config() -> None:
    decode_key(settings.MAIL_EVENT_ENCRYPTION_KEY)
    if not settings.MAIL_EVENT_ENCRYPTION_KEY_VERSION.strip():
        raise RuntimeError("MAIL_EVENT_ENCRYPTION_KEY_VERSION is missing")
    if not settings.MAIL_KAFKA_TOPIC.strip():
        raise RuntimeError("MAIL_KAFKA_TOPIC is missing")


def _cipher() -> MailEventCipher:
    return MailEventCipher(
        decode_key(settings.MAIL_EVENT_ENCRYPTION_KEY),
        settings.MAIL_EVENT_ENCRYPTION_KEY_VERSION,
    )


def build_mail_envelope(
    *,
    template_code: str,
    template_version: int,
    idempotency_key: str,
    user_id: int,
    recipient_email: str,
    variables: dict,
    request_id: str | None,
    correlation_id: str | None,
    occurred_at: datetime | None = None,
) -> dict:
    event_id = str(uuid.uuid4())
    blob = _cipher().encrypt(
        {"recipient": {"email": recipient_email}, "variables": variables},
        event_id=event_id,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "eventId": event_id,
        "eventType": EVENT_TYPE,
        "occurredAt": _timestamp(occurred_at),
        "templateCode": template_code,
        "templateVersion": template_version,
        "idempotencyKey": idempotency_key,
        "source": {"type": "USER", "id": str(user_id)},
        "requestId": request_id,
        "correlationId": correlation_id,
        "encryption": {
            "algorithm": blob.algorithm,
            "keyVersion": blob.key_version,
            "nonce": blob.nonce,
        },
        "encryptedPayload": blob.ciphertext,
    }


def _timestamp(value: datetime | None) -> str:
    current = (value or datetime.now(timezone.utc)).astimezone(timezone.utc)
    millis = current.microsecond // 1000
    return current.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"


async def enqueue_mail_command(
    session: AsyncSession,
    *,
    template_code: str,
    template_version: int,
    idempotency_key: str,
    user_id: int,
    recipient_email: str,
    variables: dict,
    request_id: str | None = None,
    correlation_id: str | None = None,
):
    payload = build_mail_envelope(
        template_code=template_code,
        template_version=template_version,
        idempotency_key=idempotency_key,
        user_id=user_id,
        recipient_email=recipient_email,
        variables=variables,
        request_id=request_id,
        correlation_id=correlation_id,
    )
    return await outbox_repository.add(
        session,
        topic=settings.MAIL_KAFKA_TOPIC,
        event_type=EVENT_TYPE,
        aggregate_type="USER",
        aggregate_id=str(user_id),
        partition_key=str(user_id),
        payload=payload,
    )
