from enum import StrEnum

from fastapi import Depends

from app.core.exceptions import ForbiddenError


class AdminPermission(StrEnum):
    READ = "ADMIN_READ"
    OPERATIONS = "ADMIN_OPERATIONS"
    FINANCE = "ADMIN_FINANCE"
    SUPER = "ADMIN_SUPER"


class AdminRole(StrEnum):
    SUPPORT = "support"
    FINANCE = "finance"
    SUPER = "super"


ROLE_PERMISSIONS: dict[str, list[str]] = {
    AdminRole.SUPPORT.value: [AdminPermission.READ.value, AdminPermission.OPERATIONS.value],
    AdminRole.FINANCE.value: [AdminPermission.READ.value, AdminPermission.FINANCE.value],
    AdminRole.SUPER.value: [
        AdminPermission.READ.value,
        AdminPermission.OPERATIONS.value,
        AdminPermission.FINANCE.value,
        AdminPermission.SUPER.value,
    ],
}


def permissions_for_role(role: str) -> list[str]:
    try:
        return list(ROLE_PERMISSIONS[role])
    except KeyError as exc:
        raise ValueError(f"Unknown admin role: {role}") from exc


def has_permission(permissions: list[str] | None, required: str) -> bool:
    granted = set(permissions or [])
    if AdminPermission.SUPER.value in granted:
        return True
    return required in granted


def require_permission(required: str):
    from app.admin.api.deps import get_current_admin

    async def _check(admin=Depends(get_current_admin)):
        if not has_permission(admin.permissions, required):
            raise ForbiddenError("Insufficient admin permission")
        return admin

    return _check
