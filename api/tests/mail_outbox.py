import json

from app.core.config import settings
from app.mail_events.crypto import MailEventCipher, decode_key
from app.modules.audit.outbox.models import AuditOutboxEvent
from sqlalchemy import select

from tests.conftest import TestingSessionLocal


def cipher() -> MailEventCipher:
    return MailEventCipher(
        decode_key(settings.MAIL_EVENT_ENCRYPTION_KEY),
        settings.MAIL_EVENT_ENCRYPTION_KEY_VERSION,
    )


async def mail_events(user_id: int, template_code: str | None = None) -> list[AuditOutboxEvent]:
    async with TestingSessionLocal() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditOutboxEvent)
                    .where(AuditOutboxEvent.aggregate_id == str(user_id))
                    .order_by(AuditOutboxEvent.id.asc())
                )
            ).scalars().all()
        )
    if template_code is None:
        return rows
    return [row for row in rows if isinstance(row.payload, dict) and row.payload.get("templateCode") == template_code]


def assert_no_plaintext(payload: dict, *secrets: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for secret in secrets:
        assert secret not in serialized
    assert "confirmUrl" not in serialized
    assert "resetUrl" not in serialized
    assert "recipient" not in serialized


def decrypt_mail(payload: dict) -> dict:
    return cipher().decrypt(
        event_id=payload["eventId"],
        nonce=payload["encryption"]["nonce"],
        ciphertext=payload["encryptedPayload"],
        key_version=payload["encryption"]["keyVersion"],
    )
