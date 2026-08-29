from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field

from app.core.ids import parse_id
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import get_current_user_id
from app.core.sessions import get_session, update_session, delete_other_user_sessions
from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.modules.users.models import User, UserRole
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.partners.models import PartnerProfile
from app.modules.system.models import UserSettings, PartnerSettings, BusinessSettings
from app.modules.auth.schemas import SessionResponse
from app.modules.auth.service import build_session_response

router = APIRouter()

PROFILE_SETTING_KEYS = ("country", "city", "telegram", "website", "password_changed_at")


class UpdateUserRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    timezone: str | None = None
    language: str | None = None
    avatar_url: str | None = None
    country: str | None = None
    city: str | None = None
    telegram: str | None = None
    website: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    logout_other_sessions: bool = False


class ContextSwitchRequest(BaseModel):
    role: str = Field(pattern="^(business|partner)$")


class AddBusinessRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str = Field(min_length=1, max_length=500)
    country: str = Field(min_length=2, max_length=3)
    category: str = Field(min_length=1, max_length=100)
    work_email: EmailStr
    phone: str = Field(min_length=5, max_length=50)
    description: str | None = Field(default=None, max_length=1000)


class AddPartnerRoleRequest(BaseModel):
    display_name: str | None = None


async def _get_user_settings(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    return dict(row.settings or {}) if row else {}


async def _upsert_user_settings(db: AsyncSession, user_id: int, updates: dict) -> dict:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    current = dict(row.settings or {}) if row else {}
    current.update(updates)
    if row:
        row.settings = current
    else:
        row = UserSettings(user_id=user_id, settings=current)
        db.add(row)
    return current


def _user_payload(user: User, extras: dict | None = None, partner: PartnerProfile | None = None) -> dict:
    extras = extras or {}
    role_since = {
        item.role: item.created_at.isoformat() if item.created_at else None
        for item in user.roles
    }
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "timezone": user.timezone,
        "language": user.language,
        "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "roles": [{"role": r.role, "status": r.status} for r in user.roles],
        "country": extras.get("country"),
        "city": extras.get("city"),
        "telegram": extras.get("telegram"),
        "website": extras.get("website"),
        "password_changed_at": extras.get("password_changed_at"),
        "partner_id": partner.id if partner else None,
        "partner_since": role_since.get("partner"),
        "business_since": role_since.get("business"),
        "payout_method": extras.get("payout_method"),
        "payout_currency": extras.get("payout_currency") or "RUB",
        "min_payout": extras.get("min_payout"),
    }


async def _session_response(db: AsyncSession, user: User, session_data: dict) -> SessionResponse:
    return await build_session_response(db, user, session_data)


async def _active_business_id(db: AsyncSession, user_id: int) -> str | None:
    membership_result = await db.execute(
        select(BusinessMembership).where(
            BusinessMembership.user_id == user_id,
            BusinessMembership.status == "active",
        )
    )
    membership = membership_result.scalars().first()
    return str(membership.business_id) if membership else None


async def _set_workspace(request: Request, db: AsyncSession, user_id: str, role: str) -> dict:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    updates: dict = {"active_role": role}
    if role == "business":
        updates["active_business_id"] = await _active_business_id(db, parse_id(user_id))
    else:
        updates["active_business_id"] = None

    await _upsert_user_settings(db, parse_id(user_id), {"last_active_role": role})
    session_data = await update_session(session_id, updates)
    if session_data is None:
        raise AppError(code="SESSION_EXPIRED", message="Session expired", status_code=401)
    return session_data


async def _activate_workspace(
    request: Request,
    db: AsyncSession,
    user_id: str,
    new_role: str,
    had_roles: bool,
) -> dict:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    current = await get_session(session_id) if session_id else None
    if current is None:
        raise AppError(code="SESSION_EXPIRED", message="Session expired", status_code=401)
    if had_roles and current.get("active_role"):
        return current
    return await _set_workspace(request, db, user_id, new_role)


@router.get("")
async def get_me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == parse_id(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)

    extras = await _get_user_settings(db, user.id)
    partner_result = await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == user.id))
    partner = partner_result.scalar_one_or_none()
    if partner:
        settings_result = await db.execute(
            select(PartnerSettings).where(PartnerSettings.partner_id == partner.id)
        )
        partner_settings = settings_result.scalar_one_or_none()
        payload = dict(partner_settings.settings or {}) if partner_settings else {}
        extras["payout_method"] = payload.get("payout_method")
        extras["payout_currency"] = payload.get("payout_currency")
        extras["min_payout"] = payload.get("min_payout")

    return _user_payload(user, extras, partner)


@router.patch("")
async def update_me(
    data: UpdateUserRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == parse_id(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)

    payload = data.model_dump(exclude_unset=True)
    user_fields = {
        key: payload.pop(key)
        for key in ("first_name", "last_name", "phone", "timezone", "language", "avatar_url")
        if key in payload
    }
    for key, value in user_fields.items():
        setattr(user, key, value)

    extras = await _get_user_settings(db, user.id)
    setting_updates = {key: payload[key] for key in PROFILE_SETTING_KEYS if key in payload}
    if setting_updates:
        extras = await _upsert_user_settings(db, user.id, setting_updates)

    partner_result = await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == user.id))
    partner = partner_result.scalar_one_or_none()
    return _user_payload(user, extras, partner)


@router.post("/password")
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == parse_id(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(code="INVALID_CREDENTIALS", message="Current password is incorrect", status_code=400)
    if data.current_password == data.new_password:
        raise AppError(code="SAME_PASSWORD", message="New password must be different", status_code=400)

    user.password_hash = hash_password(data.new_password)
    from datetime import datetime, timezone
    await _upsert_user_settings(db, user.id, {
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
    })

    if data.logout_other_sessions:
        session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if session_id:
            await delete_other_user_sessions(user_id, session_id)

    return {"status": "ok"}


@router.post("/context")
async def switch_context(
    data: ContextSwitchRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == parse_id(user_id),
            UserRole.role == data.role,
            UserRole.status == "active",
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise AppError(code="ROLE_NOT_FOUND", message="Role not available", status_code=403)

    session_data = await _set_workspace(request, db, user_id, data.role)
    user_result = await db.execute(select(User).where(User.id == parse_id(user_id)))
    return await _session_response(db, user_result.scalar_one(), session_data)


@router.post("/roles/business")
async def add_business_role(
    data: AddBusinessRoleRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.execute(select(User).where(User.id == parse_id(user_id)))
    user = user.scalar_one_or_none()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)

    had_roles = any(item.status == "active" for item in user.roles)
    existing_role = next((item for item in user.roles if item.role == "business"), None)

    if not existing_role:
        db.add(UserRole(user_id=user.id, role="business", status="active"))
        business = Business(name=data.name.strip(), country=data.country.upper())
        db.add(business)
        await db.flush()
        db.add(
            BusinessMembership(
                business_id=business.id,
                user_id=user.id,
                permission_role="owner",
                status="active",
            )
        )
        db.add(
            BusinessSettings(
                business_id=business.id,
                settings={
                    "website": data.website.strip(),
                    "category": data.category.strip(),
                    "work_email": str(data.work_email).lower(),
                    "phone": data.phone.strip(),
                    "description": (data.description or "").strip() or None,
                },
            )
        )
        if not user.phone:
            user.phone = data.phone.strip()
        await db.flush()
        await db.refresh(user, ["roles"])

    session_data = await _activate_workspace(request, db, user_id, "business", had_roles)
    return await _session_response(db, user, session_data)


@router.post("/roles/partner")
async def add_partner_role(
    data: AddPartnerRoleRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.id == parse_id(user_id)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found", status_code=404)

    had_roles = any(item.status == "active" for item in user.roles)
    existing_role = next((item for item in user.roles if item.role == "partner"), None)

    if not existing_role:
        db.add(UserRole(user_id=user.id, role="partner", status="active"))
        display_name = (data.display_name or f"{user.first_name or ''} {user.last_name or ''}").strip()
        if not display_name:
            display_name = user.email.split("@")[0]
        existing_profile = await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == user.id))
        if not existing_profile.scalar_one_or_none():
            db.add(
                PartnerProfile(
                    user_id=user.id,
                    display_name=display_name,
                    status="active",
                )
            )
        await db.flush()
        await db.refresh(user, ["roles"])

    session_data = await _activate_workspace(request, db, user_id, "partner", had_roles)
    return await _session_response(db, user, session_data)
