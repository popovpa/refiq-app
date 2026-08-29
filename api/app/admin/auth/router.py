from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.api.deps import get_current_admin
from app.admin.auth.service import AdminAuthService
from app.admin.auth.sessions import delete_admin_session
from app.admin.schemas import AdminLoginRequest, AdminSessionResponse
from app.core.config import settings
from app.core.database import get_db


router = APIRouter()


def serialize_admin(admin) -> AdminSessionResponse:
    return AdminSessionResponse(
        id=admin.id,
        email=admin.email,
        role=admin.role,
        permissions=list(admin.permissions or []),
        status=admin.status,
        last_login_at=admin.last_login_at,
    )


def set_admin_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.ADMIN_SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.ADMIN_SESSION_COOKIE_SECURE or settings.is_production,
        samesite="strict",
        max_age=settings.SESSION_TTL_SECONDS,
        path="/",
    )


@router.post("/login", response_model=AdminSessionResponse)
async def login(data: AdminLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    admin, session_id = await AdminAuthService(db).login(data.email, data.password)
    set_admin_cookie(response, session_id)
    return serialize_admin(admin)


@router.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get(settings.ADMIN_SESSION_COOKIE_NAME)
    if session_id:
        await delete_admin_session(session_id)
    response.delete_cookie(
        settings.ADMIN_SESSION_COOKIE_NAME,
        path="/",
        samesite="strict",
        secure=settings.ADMIN_SESSION_COOKIE_SECURE or settings.is_production,
    )
    return {"status": "ok"}


@router.get("/session", response_model=AdminSessionResponse)
async def session(admin=Depends(get_current_admin)):
    return serialize_admin(admin)
