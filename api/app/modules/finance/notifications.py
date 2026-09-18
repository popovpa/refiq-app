from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.enums import NotificationSeverity, NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.payouts.models import Payout

PAYOUT_DESTINATION = "/business/payouts"


async def send_payout_notifications(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    service = NotificationService(db)
    sent = 0
    payouts = (
        await db.execute(
            select(Payout).where(
                Payout.status.in_(["created", "awaiting_confirmation", "pending", "overdue"]),
                Payout.payer_business_id.is_not(None),
            )
        )
    ).scalars().all()
    day = now.date().isoformat()
    slot = "am" if now.hour < 12 else "pm"
    for payout in payouts:
        if payout.status == "overdue":
            created = await service.notify_business(
                payout.payer_business_id,
                type=NotificationType.PAYOUT_OVERDUE,
                message=f"Просрочена выплата партнёру на {payout.amount} ₽",
                metadata={"payout_id": payout.id},
                destination=PAYOUT_DESTINATION,
                dedupe_key=f"payout_overdue:{payout.id}",
            )
            traffic = await service.notify_business(
                payout.payer_business_id,
                type=NotificationType.PARTNER_TRAFFIC_SUSPENDED,
                message="Партнёрский трафик приостановлен из-за просроченной выплаты",
                metadata={"payout_id": payout.id},
                destination=PAYOUT_DESTINATION,
                dedupe_key=f"traffic_suspended:{payout.payer_business_id}:{payout.id}",
            )
            sent += len(created) + len(traffic)
            continue
        ntype = NotificationType.PAYOUT_DUE if payout.created_at and payout.created_at.date() == now.date() else NotificationType.PAYOUT_REMINDER
        created = await service.notify_business(
            payout.payer_business_id,
            type=ntype,
            message=f"Подтвердите выплату партнёру на {payout.amount} ₽",
            metadata={"payout_id": payout.id},
            destination=PAYOUT_DESTINATION,
            dedupe_key=f"payout_reminder:{payout.id}:{day}:{slot}",
        )
        sent += len(created)
    return sent
