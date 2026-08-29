from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.sessions import get_session


async def get_current_user_id(request: Request) -> str:
    from app.core.config import settings
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session_data = await get_session(session_id)
    if session_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session_data["user_id"]


async def get_session_data(request: Request) -> dict:
    from app.core.config import settings
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session_data = await get_session(session_id)
    if session_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session_data


async def require_business_role(session_data: dict = Depends(get_session_data)) -> dict:
    if session_data.get("active_role") != "business":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business role required")
    if not session_data.get("active_business_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active business")
    return session_data


async def require_partner_role(session_data: dict = Depends(get_session_data)) -> dict:
    if session_data.get("active_role") != "partner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Partner role required")
    return session_data
