import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import AuditLog
from app.modules.users.models import User


def actor_display_name(user: User | None) -> str:
    if not user:
        return "Пользователь"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if name:
        return name
    return user.email.split("@")[0]


async def write_audit_log(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_id=f"evt_{uuid.uuid4().hex}",
        schema_version=1,
        event_type=action,
        action=action[:64],
        occurred_at=datetime.now(timezone.utc),
        actor_type="USER" if user_id is not None else "SYSTEM",
        actor_id=str(user_id) if user_id is not None else None,
        entity_type=resource_type or "UNKNOWN",
        entity_id=resource_id or "-",
        ip_address=ip_address,
        metadata_=details,
    )
    db.add(entry)
    return entry
