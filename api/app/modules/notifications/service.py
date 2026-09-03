from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses.models import BusinessMembership
from app.modules.notifications.enums import NotificationSeverity, NotificationType
from app.modules.notifications.models import Notification
from app.modules.notifications.registry import default_destination, default_severity, default_title
from app.modules.sites.models import Site


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        user_id: int,
        type: NotificationType | str,
        title: str | None = None,
        message: str | None = None,
        severity: NotificationSeverity | str | None = None,
        destination: str | None = None,
        metadata: dict[str, Any] | None = None,
        role_context: str | None = None,
        business_id: int | None = None,
        partner_id: int | None = None,
        dedupe_key: str | None = None,
    ) -> Notification | None:
        typed = type if isinstance(type, NotificationType) else NotificationType(type)
        meta = metadata or {}
        if dedupe_key:
            existing = await self.db.scalar(
                select(Notification.id).where(
                    Notification.user_id == user_id,
                    Notification.dedupe_key == dedupe_key,
                )
            )
            if existing:
                return None
        item = Notification(
            user_id=user_id,
            role_context=role_context,
            business_id=business_id,
            partner_id=partner_id,
            type=typed.value,
            severity=(severity.value if isinstance(severity, NotificationSeverity) else severity)
            or default_severity(typed).value,
            title=title or default_title(typed),
            message=message,
            is_read=False,
            destination=destination if destination is not None else default_destination(typed, meta),
            metadata_json=meta or None,
            dedupe_key=dedupe_key,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def notify_business(
        self,
        business_id: int,
        *,
        type: NotificationType | str,
        title: str | None = None,
        message: str | None = None,
        severity: NotificationSeverity | str | None = None,
        destination: str | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> list[Notification]:
        user_ids = list(
            (
                await self.db.execute(
                    select(BusinessMembership.user_id).where(
                        BusinessMembership.business_id == business_id,
                        BusinessMembership.status == "active",
                    )
                )
            ).scalars()
        )
        created: list[Notification] = []
        for user_id in user_ids:
            item = await self.create(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                severity=severity,
                destination=destination,
                metadata=metadata,
                role_context="business",
                business_id=business_id,
                dedupe_key=f"{dedupe_key}:u{user_id}" if dedupe_key else None,
            )
            if item:
                created.append(item)
        return created

    async def notify_sdk_connected(self, *, business_id: int, site_id: int | None, domain: str | None) -> None:
        meta = {"site_id": site_id, "domain": domain}
        await self.notify_business(
            business_id,
            type=NotificationType.SDK_CONNECTED,
            message=domain,
            metadata=meta,
            dedupe_key=f"sdk_connected:{site_id or business_id}",
        )

    async def notify_postback_failed(self, *, business_id: int, reason_code: str | None) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        await self.notify_business(
            business_id,
            type=NotificationType.POSTBACK_FAILED,
            message=reason_code,
            metadata={"reason_code": reason_code},
            dedupe_key=f"postback_failed:{business_id}:{reason_code}:{day}",
        )

    def _scope_filters(
        self,
        user_id: int,
        *,
        role_context: str | None,
        business_id: int | None,
        partner_id: int | None,
    ) -> list:
        filters = [Notification.user_id == user_id]
        if role_context == "business":
            business_match = Notification.business_id.is_(None)
            if business_id:
                business_match = or_(Notification.business_id.is_(None), Notification.business_id == business_id)
            filters.append(
                or_(
                    Notification.role_context.is_(None),
                    (Notification.role_context == "business") & business_match,
                )
            )
        elif role_context == "partner":
            partner_match = Notification.partner_id.is_(None)
            if partner_id:
                partner_match = or_(Notification.partner_id.is_(None), Notification.partner_id == partner_id)
            filters.append(
                or_(
                    Notification.role_context.is_(None),
                    (Notification.role_context == "partner") & partner_match,
                )
            )
        return filters

    async def unread_count(
        self, user_id: int, *, role_context: str | None, business_id: int | None, partner_id: int | None
    ) -> int:
        filters = self._scope_filters(
            user_id, role_context=role_context, business_id=business_id, partner_id=partner_id
        )
        return int(
            await self.db.scalar(
                select(func.count(Notification.id)).where(*filters, Notification.is_read.is_(False))
            )
            or 0
        )

    async def list_notifications(
        self,
        user_id: int,
        *,
        role_context: str | None,
        business_id: int | None,
        partner_id: int | None,
        limit: int = 20,
    ) -> list[Notification]:
        filters = self._scope_filters(
            user_id, role_context=role_context, business_id=business_id, partner_id=partner_id
        )
        result = await self.db.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_read(self, user_id: int, notification_id: int) -> Notification | None:
        item = await self.db.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        if not item:
            return None
        if not item.is_read:
            item.is_read = True
            item.read_at = datetime.now(timezone.utc)
            await self.db.flush()
        return item

    async def mark_all_read(
        self, user_id: int, *, role_context: str | None, business_id: int | None, partner_id: int | None
    ) -> int:
        filters = self._scope_filters(
            user_id, role_context=role_context, business_id=business_id, partner_id=partner_id
        )
        result = await self.db.execute(
            update(Notification)
            .where(*filters, Notification.is_read.is_(False))
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)


async def site_domain(db: AsyncSession, site_id: int | None) -> tuple[int | None, str | None]:
    if not site_id:
        return None, None
    site = await db.scalar(select(Site).where(Site.id == site_id))
    if not site:
        return site_id, None
    return site.id, site.domain
