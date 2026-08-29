from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit.models import AdminAuditEvent
from app.admin.auth.models import AdminUser


async def record_admin_action(
    db: AsyncSession,
    *,
    admin: AdminUser,
    action: str,
    entity_type: str,
    entity_id: str | int,
    reason: str,
    details: dict | None = None,
) -> AdminAuditEvent:
    event = AdminAuditEvent(
        admin_user_id=admin.id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        reason=reason.strip(),
        details=details,
    )
    db.add(event)
    await db.flush()
    return event
