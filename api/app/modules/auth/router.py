from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import get_current_user_id, get_session_data
from app.core.sessions import delete_session, delete_all_user_sessions
from .email_confirmation import EmailConfirmationService
from .password_reset import PasswordResetService
from .schemas import (
    ConfirmEmailRequest,
    ConfirmEmailResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SessionResponse,
)
from .service import AuthService, build_session_response

router = APIRouter()


def _set_session_cookie(response: Response, session_id: str):
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.SESSION_TTL_SECONDS,
        path="/",
    )


@router.post("/register", response_model=RegisterResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.register(data)
    return {
        "status": "ok",
        "message": "Мы отправили письмо для подтверждения аккаунта.",
    }


@router.post("/login", response_model=SessionResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user, session_id, session_data = await service.login(data)
    _set_session_cookie(response, session_id)
    return await build_session_response(db, user, session_data)


@router.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_id:
        await delete_session(session_id)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    user_id: str = Depends(get_current_user_id),
):
    await delete_all_user_sessions(user_id)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.post("/confirm-email", response_model=ConfirmEmailResponse)
async def confirm_email(data: ConfirmEmailRequest, db: AsyncSession = Depends(get_db)):
    service = EmailConfirmationService(db)
    return await service.confirm(data.token)


@router.post("/confirm-email/login", response_model=SessionResponse)
async def confirm_email_login(
    data: ConfirmEmailRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    service = EmailConfirmationService(db)
    user, session_id, session_data = await service.confirm_and_login(data.token)
    _set_session_cookie(response, session_id)
    return await build_session_response(db, user, session_data)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = PasswordResetService(db)
    return await service.request_reset(data.email)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = PasswordResetService(db)
    return await service.reset_password(data.token, data.password)


@router.get("/session", response_model=SessionResponse)
async def get_session_endpoint(
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    user = await service.get_user_by_id(session_data["user_id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return await build_session_response(db, user, session_data)
