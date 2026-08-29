from app.core.ids import parse_id
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, verify_password, generate_session_id
from app.core.sessions import create_session
from app.core.exceptions import AppError, ConflictError
from app.modules.users.models import User
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.partners.models import PartnerProfile
from app.modules.system.models import UserSettings
from .schemas import RegisterRequest, LoginRequest, SessionResponse, UserResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> User:
        email = data.email.lower().strip()

        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictError("User with this email already exists")

        user = User(
            email=email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            status="new",
        )
        self.db.add(user)
        await self.db.flush()

        from app.modules.auth.email_confirmation import EmailConfirmationService

        await EmailConfirmationService(self.db).issue(user)
        await self.db.refresh(user, ["roles"])
        return user

    async def login(self, data: LoginRequest) -> tuple[User, str, dict]:
        email = data.email.lower().strip()

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise AppError(code="INVALID_CREDENTIALS", message="Invalid email or password", status_code=401)

        if not verify_password(data.password, user.password_hash):
            raise AppError(code="INVALID_CREDENTIALS", message="Invalid email or password", status_code=401)

        if user.status == "new":
            raise AppError(
                code="ACCOUNT_NOT_CONFIRMED",
                message="Подтвердите аккаунт по ссылке из письма.",
                status_code=403,
            )

        if user.status != "active":
            raise AppError(code="ACCOUNT_SUSPENDED", message="Account is suspended", status_code=403)

        active_role, active_business_id = await self.resolve_workspace(user)

        session_id = generate_session_id()
        session_data = await create_session(
            session_id=session_id,
            user_id=str(user.id),
            active_role=active_role,
            active_business_id=active_business_id,
        )

        return user, session_id, session_data

    async def resolve_workspace(self, user: User) -> tuple[str | None, str | None]:
        roles = [r.role for r in user.roles if r.status == "active"]
        if not roles:
            return None, None

        preferred = await self._preferred_role(user.id)
        if preferred in roles:
            active_role = preferred
        elif len(roles) == 1:
            active_role = roles[0]
        elif "business" in roles:
            active_role = "business"
        else:
            active_role = roles[0]

        active_business_id = None
        if active_role == "business":
            membership_result = await self.db.execute(
                select(BusinessMembership).where(
                    BusinessMembership.user_id == user.id,
                    BusinessMembership.status == "active",
                )
            )
            membership = membership_result.scalars().first()
            if membership:
                active_business_id = str(membership.business_id)

        return active_role, active_business_id

    async def _preferred_role(self, user_id: int) -> str | None:
        result = await self.db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        value = (row.settings or {}).get("last_active_role")
        return value if value in {"business", "partner"} else None

    async def get_user_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.id == parse_id(user_id)))
        return result.scalar_one_or_none()


def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        phone=user.phone,
        timezone=user.timezone,
        language=user.language,
        email_verified_at=user.email_verified_at.isoformat() if user.email_verified_at else None,
        status=user.status,
        roles=[{"role": r.role, "status": r.status} for r in user.roles],
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


async def load_workspace_names(db: AsyncSession, user_id: int) -> tuple[str | None, str | None]:
    business_name = await db.scalar(
        select(Business.name)
        .join(BusinessMembership, BusinessMembership.business_id == Business.id)
        .where(
            BusinessMembership.user_id == user_id,
            BusinessMembership.status == "active",
        )
        .order_by(BusinessMembership.id.asc())
        .limit(1)
    )
    partner_name = await db.scalar(
        select(PartnerProfile.display_name).where(PartnerProfile.user_id == user_id)
    )
    return business_name, partner_name


async def build_session_response(db: AsyncSession, user: User, session_data: dict) -> SessionResponse:
    business_name, partner_name = await load_workspace_names(db, user.id)
    return SessionResponse(
        user=user_to_response(user),
        active_role=session_data.get("active_role"),
        active_business_id=session_data.get("active_business_id"),
        business_name=business_name,
        partner_name=partner_name,
    )
