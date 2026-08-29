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
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry
