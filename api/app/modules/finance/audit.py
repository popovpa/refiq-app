from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinancialAuditEvent


_SECRET_KEYS = {
    "password",
    "token",
    "secret",
    "card",
    "bank_account",
    "account",
    "pan",
    "cvv",
    "provider_token",
}


def sanitize_metadata(metadata: dict | None) -> dict | None:
    if not metadata:
        return None
    cleaned = {}
    for key, value in metadata.items():
        lowered = str(key).lower()
        if any(part in lowered for part in _SECRET_KEYS):
            cleaned[key] = "[redacted]"
        else:
            cleaned[key] = value
    return cleaned


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor_user_id: int | None = None,
    system_actor: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> FinancialAuditEvent:
    event = FinancialAuditEvent(
        actor_user_id=actor_user_id,
        system_actor=system_actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        metadata_=sanitize_metadata(metadata),
    )
    db.add(event)
    await db.flush()
    return event
