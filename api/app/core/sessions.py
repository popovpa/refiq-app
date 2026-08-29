import json
from datetime import datetime, timezone

from app.core.config import settings
from app.core.redis import redis_client


SESSION_PREFIX = "session:"


def _normalize_session_payload(data: dict) -> dict:
    if data.get("user_id") is not None:
        data["user_id"] = str(data["user_id"])
    if data.get("active_business_id") is not None:
        data["active_business_id"] = str(data["active_business_id"])
    return data


async def create_session(
    session_id: str,
    user_id: str,
    active_role: str | None = None,
    active_business_id: str | None = None,
) -> dict:
    data = _normalize_session_payload({
        "user_id": user_id,
        "active_role": active_role,
        "active_business_id": active_business_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
    })
    await redis_client.set(
        f"{SESSION_PREFIX}{session_id}",
        json.dumps(data),
        ex=settings.SESSION_TTL_SECONDS,
    )
    return data


async def get_session(session_id: str) -> dict | None:
    data = await redis_client.get(f"{SESSION_PREFIX}{session_id}")
    if data is None:
        return None
    return _normalize_session_payload(json.loads(data))


async def update_session(session_id: str, updates: dict) -> dict | None:
    data = await get_session(session_id)
    if data is None:
        return None
    data.update(updates)
    data["last_activity_at"] = datetime.now(timezone.utc).isoformat()
    data = _normalize_session_payload(data)
    await redis_client.set(
        f"{SESSION_PREFIX}{session_id}",
        json.dumps(data),
        ex=settings.SESSION_TTL_SECONDS,
    )
    return data


async def delete_session(session_id: str) -> None:
    await redis_client.delete(f"{SESSION_PREFIX}{session_id}")


async def delete_other_user_sessions(user_id: str, keep_session_id: str) -> int:
    count = 0
    keep_key = f"{SESSION_PREFIX}{keep_session_id}"
    async for key in redis_client.scan_iter(f"{SESSION_PREFIX}*"):
        if key == keep_key:
            continue
        data = await redis_client.get(key)
        if data:
            session_data = json.loads(data)
            if str(session_data.get("user_id")) == str(user_id):
                await redis_client.delete(key)
                count += 1
    return count


async def delete_all_user_sessions(user_id: str) -> int:
    count = 0
    async for key in redis_client.scan_iter(f"{SESSION_PREFIX}*"):
        data = await redis_client.get(key)
        if data:
            session_data = json.loads(data)
            if str(session_data.get("user_id")) == str(user_id):
                await redis_client.delete(key)
                count += 1
    return count
