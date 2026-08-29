from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.models import AdminUser
from app.admin.auth.sessions import create_admin_session
from app.admin.permissions import permissions_for_role
from app.core.exceptions import AppError
from app.core.security import generate_session_id, hash_password, verify_password


class AdminAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, admin_id: int) -> AdminUser | None:
        return await self.db.get(AdminUser, admin_id)

    async def get_by_email(self, email: str) -> AdminUser | None:
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def create(self, email: str, password: str, role: str) -> AdminUser:
        normalized = email.strip().lower()
        existing = await self.get_by_email(normalized)
        if existing:
            raise AppError("CONFLICT", "Admin user already exists", 409)
        admin = AdminUser(
            email=normalized,
            password_hash=hash_password(password),
            status="active",
            role=role,
            permissions=permissions_for_role(role),
        )
        self.db.add(admin)
        await self.db.flush()
        return admin

    async def login(self, email: str, password: str) -> tuple[AdminUser, str]:
        admin = await self.get_by_email(email)
        if not admin or not verify_password(password, admin.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Invalid email or password", 401)
        if admin.status != "active":
            raise AppError("ACCOUNT_SUSPENDED", "Admin account is suspended", 403)
        admin.last_login_at = datetime.now(timezone.utc)
        session_id = generate_session_id()
        await create_admin_session(session_id, admin.id)
        return admin, session_id
