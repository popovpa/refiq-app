from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import FinancePermission, MembershipRole, MembershipStatus
from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.core.ids import parse_id
from app.core.permissions import get_session_data
from app.modules.businesses.models import BusinessMembership
from app.modules.partners.models import PartnerProfile

ROLE_PERMISSIONS: dict[str, frozenset[FinancePermission]] = {
    MembershipRole.OWNER.value: frozenset(FinancePermission),
    MembershipRole.ADMIN.value: frozenset(FinancePermission),
    MembershipRole.MANAGER.value: frozenset(
        {FinancePermission.FINANCE_VIEW, FinancePermission.PAYOUT_VIEW}
    ),
    MembershipRole.VIEWER.value: frozenset({FinancePermission.FINANCE_VIEW}),
}


def has_finance_permission(role: str | None, permission: FinancePermission) -> bool:
    granted = ROLE_PERMISSIONS.get(role or "")
    if not granted:
        return False
    return permission in granted


async def load_business_membership(
    db: AsyncSession, user_id: int, business_id: int
) -> BusinessMembership | None:
    return await db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.user_id == user_id,
            BusinessMembership.business_id == business_id,
            BusinessMembership.status == MembershipStatus.ACTIVE.value,
        )
    )


def require_business_finance(permission: FinancePermission):
    async def dependency(
        session_data: dict = Depends(get_session_data),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        user_id = parse_id(session_data["user_id"])
        business_id = session_data.get("active_business_id")
        if not business_id:
            raise ForbiddenError("No active business")
        membership = await load_business_membership(db, user_id, parse_id(business_id))
        if not membership:
            raise ForbiddenError("Business membership required")
        if not has_finance_permission(membership.permission_role, permission):
            raise ForbiddenError("Insufficient finance permission")
        session_data["_membership_role"] = membership.permission_role
        return session_data

    return dependency


async def require_partner_profile(
    session_data: dict = Depends(get_session_data),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = parse_id(session_data["user_id"])
    profile = await db.scalar(select(PartnerProfile).where(PartnerProfile.user_id == user_id))
    if not profile:
        raise ForbiddenError("Partner profile required")
    session_data["_partner_id"] = profile.id
    return session_data
