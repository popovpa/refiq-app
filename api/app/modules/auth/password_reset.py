from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import hash_password
from app.core.sessions import delete_all_user_sessions
from app.modules.auth.models import PasswordResetToken
from app.modules.email.service import EmailService
from app.modules.users.models import User

logger = structlog.get_logger()

TOKEN_BYTES = 32
TTL = timedelta(minutes=30)
INVALID_TOKEN_MESSAGE = "Ссылка недействительна или уже использована."
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 900
GENERIC_OK = {
    "status": "ok",
    "message": "Если аккаунт с таким email существует, мы отправили ссылку для восстановления пароля.",
}


def generate_reset_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_reset_token(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _reset_url(token: str) -> str:
    return f"{settings.public_app_url}/reset-password?token={token}"


def _rate_key(email: str) -> str:
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"pwdreset:{digest}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class PasswordResetService:
    def __init__(self, db: AsyncSession, email: EmailService | None = None):
        self.db = db
        self.email = email or EmailService()

    async def request_reset(self, email: str) -> dict:
        normalized = email.lower().strip()
        await self._enforce_rate_limit(normalized)

        user = (
            await self.db.execute(select(User).where(User.email == normalized))
        ).scalar_one_or_none()
        if not user or user.status != "active":
            return GENERIC_OK

        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
            .execution_options(synchronize_session=False)
        )

        plaintext = generate_reset_token()
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(plaintext),
            expires_at=now + TTL,
        )
        self.db.add(token)
        await self.db.flush()

        try:
            await self.email.send_password_reset(
                to=user.email,
                reset_url=_reset_url(plaintext),
                ttl_minutes=int(TTL.total_seconds() // 60),
            )
        except Exception:
            logger.exception("password_reset_email_failed", user_id=user.id)

        return GENERIC_OK

    async def reset_password(self, token: str, password: str) -> dict:
        now = datetime.now(timezone.utc)
        token_hash = hash_reset_token(token.strip())
        row = (
            await self.db.execute(
                select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if not row or row.used_at is not None or _as_utc(row.expires_at) <= now:
            raise AppError("RESET_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)

        claimed = (
            await self.db.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.id == row.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=now)
                .returning(PasswordResetToken.id)
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()
        if claimed is None:
            raise AppError("RESET_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)

        user = (
            await self.db.execute(select(User).where(User.id == row.user_id))
        ).scalar_one_or_none()
        if not user or user.status != "active":
            raise AppError("RESET_TOKEN_INVALID", INVALID_TOKEN_MESSAGE, 400)

        user.password_hash = hash_password(password)
        await delete_all_user_sessions(str(user.id))
        return {"status": "ok", "message": "Пароль успешно изменён"}

    async def _enforce_rate_limit(self, email: str) -> None:
        from app.core.redis import redis_client

        key = _rate_key(email)
        count = int(await redis_client.incr(key))
        if count == 1:
            await redis_client.expire(key, RATE_LIMIT_WINDOW_SECONDS)
        if count > RATE_LIMIT_MAX:
            raise AppError(
                "TOO_MANY_REQUESTS",
                "Слишком много запросов. Попробуйте позже.",
                429,
            )
