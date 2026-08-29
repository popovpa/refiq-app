import json
from datetime import datetime, timezone

from app.core.config import settings
from app.core.redis import redis_client

SESSION_PREFIX = "admin_session:"


async def create_admin_session(session_id: str, admin_user_id: int) -> dict:
    data = {
        "admin_user_id": str(admin_user_id),
        "kind": "admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_client.set(
        f"{SESSION_PREFIX}{session_id}",
        json.dumps(data),
        ex=settings.SESSION_TTL_SECONDS,
    )
    return data


async def get_admin_session(session_id: str) -> dict | None:
    raw = await redis_client.get(f"{SESSION_PREFIX}{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def delete_admin_session(session_id: str) -> None:
    await redis_client.delete(f"{SESSION_PREFIX}{session_id}")
