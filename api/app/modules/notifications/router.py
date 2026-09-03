from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ids import parse_id, parse_optional_id
from app.core.permissions import get_session_data
from app.modules.notifications.service import NotificationService

router = APIRouter()


def _scope(session_data: dict) -> dict:
    role = session_data.get("active_role")
    return {
        "role_context": role if role in {"business", "partner"} else None,
        "business_id": parse_optional_id(session_data.get("active_business_id")),
        "partner_id": parse_optional_id(session_data.get("active_partner_id")),
    }


def _serialize(item) -> dict:
    return {
        "id": item.id,
        "type": item.type,
        "severity": item.severity,
        "title": item.title,
        "message": item.message,
        "is_read": item.is_read,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "read_at": item.read_at.isoformat() if item.read_at else None,
        "destination": item.destination,
        "metadata": item.metadata_json or {},
        "role_context": item.role_context,
        "business_id": item.business_id,
        "partner_id": item.partner_id,
    }


@router.get("/unread-count")
async def unread_count(
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    user_id = parse_id(session_data["user_id"])
    count = await NotificationService(db).unread_count(user_id, **_scope(session_data))
    return {"unread_count": count}


@router.get("")
@router.get("/")
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    user_id = parse_id(session_data["user_id"])
    items = await NotificationService(db).list_notifications(
        user_id, limit=limit, **_scope(session_data)
    )
    return {"items": [_serialize(item) for item in items]}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    user_id = parse_id(session_data["user_id"])
    item = await NotificationService(db).mark_read(user_id, notification_id)
    if not item:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Notification")
    unread = await NotificationService(db).unread_count(user_id, **_scope(session_data))
    return {"notification": _serialize(item), "unread_count": unread}


@router.post("/read-all")
async def mark_all_read(
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    user_id = parse_id(session_data["user_id"])
    service = NotificationService(db)
    updated = await service.mark_all_read(user_id, **_scope(session_data))
    return {"updated": updated, "unread_count": 0}
