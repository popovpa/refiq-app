from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import generate_session_id
from app.core.sessions import create_session
from app.modules.auth.models import EmailConfirmationToken
from app.modules.auth.password_reset import _as_utc, generate_reset_token, hash_reset_token
from app.modules.email.service import EmailService
from app.modules.users.models import User

logger = structlog.get_logger()

TTL = timedelta(hours=24)
TTL_HOURS = 24
INVALID_TOKEN_MESSAGE = "Ссылка недействительна или уже использована."
CONFIRMED_OK = {"status": "ok", "message": "Аккаунт подтверждён"}


def _confirm_url(token: str) -> str:
    return f"{settings.public_app_url}/confirm-account?token={token}"


class EmailConfirmationService:
    def __init__(self, db: AsyncSession, email: EmailService | None = None):
        self.db = db
        self.email = email or EmailService()

    async def issue(self, user: User) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(EmailConfirmationToken)
            .where(
                EmailConfirmationToken.user_id == user.id,
                EmailConfirmationToken.used_at.is_(None),
            )
            .values(used_at=now)
            .execution_options(synchronize_session=False)
        )
        plaintext = generate_reset_token()
        self.db.add(
            EmailConfirmationToken(
                user_id=user.id,
                token_hash=hash_reset_token(plaintext),
                expires_at=now + TTL,
            )
        )
        await self.db.flush()
        try:
            await self.email.send_account_confirmation(
                to=user.email,
                confirm_url=_confirm_url(plaintext),
                ttl_hours=TTL_HOURS,
            )
        except Exception:
            logger.exception("account_confirmation_email_failed", user_id=user.id)

    async def confirm(self, token: str) -> dict:
        _row, user = await self._valid_token_and_user(token)
        await self._activate(user)
        return CONFIRMED_OK

    async def confirm_and_login(self, token: str) -> tuple[User, str, dict]:
        now = datetime.now(timezone.utc)
        row, user = await self._valid_token_and_user(token)
        claimed = (
            await self.db.execute(
                update(EmailConfirmationToken)
                .where(
                    EmailConfirmationToken.id == row.id,
                    EmailConfirmationToken.used_at.is_(None),
                )
                .values(used_at=now)
                .returning(EmailConfirmationToken.id)
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()
        if claimed is None:
            raise AppError("CONFIRM_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)

        await self._activate(user)
        await self.db.refresh(user, ["roles"])

        from app.modules.auth.service import AuthService

        active_role, active_business_id = await AuthService(self.db).resolve_workspace(user)
        session_id = generate_session_id()
        session_data = await create_session(
            session_id=session_id,
            user_id=str(user.id),
            active_role=active_role,
            active_business_id=active_business_id,
        )
        return user, session_id, session_data

    async def _valid_token_and_user(self, token: str) -> tuple[EmailConfirmationToken, User]:
        now = datetime.now(timezone.utc)
        token_hash = hash_reset_token(token.strip())
        row = (
            await self.db.execute(
                select(EmailConfirmationToken).where(EmailConfirmationToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if not row or row.used_at is not None or _as_utc(row.expires_at) <= now:
            raise AppError("CONFIRM_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)
        user = (
            await self.db.execute(select(User).where(User.id == row.user_id))
        ).scalar_one_or_none()
        if not user or user.status not in {"new", "active"}:
            raise AppError("CONFIRM_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)
        return row, user

    async def _activate(self, user: User) -> None:
        now = datetime.now(timezone.utc)
        if user.status == "new":
            user.status = "active"
        if user.email_verified_at is None:
            user.email_verified_at = now
