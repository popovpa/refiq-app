from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.models import AdminUser
from app.admin.auth.service import AdminAuthService
from app.admin.auth.sessions import get_admin_session
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.ids import parse_id


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    session_id = request.cookies.get(settings.ADMIN_SESSION_COOKIE_NAME)
    if not session_id:
        raise AppError("NOT_AUTHENTICATED", "Not authenticated", 401)
    session = await get_admin_session(session_id)
    if not session or session.get("kind") != "admin":
        raise AppError("NOT_AUTHENTICATED", "Session expired", 401)
    admin = await AdminAuthService(db).get_by_id(parse_id(session["admin_user_id"]))
    if not admin or admin.status != "active":
        raise AppError("NOT_AUTHENTICATED", "Session expired", 401)
    return admin
