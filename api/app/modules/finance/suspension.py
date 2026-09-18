from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import PayoutFailureClass, PayoutStatus
from app.modules.finance.audit import record_audit
from app.modules.finance.models import PartnerTrafficSuspension
from app.modules.payouts.models import Payout

BUSINESS_FAULT = {
    PayoutFailureClass.BUSINESS_NO_FUNDS.value,
    PayoutFailureClass.BUSINESS_NOT_CONFIRMED.value,
    PayoutFailureClass.BUSINESS_PAYMENT_ACCOUNT_INVALID.value,
}


def is_business_fault(failure_class: str | None) -> bool:
    if not failure_class:
        return True
    return failure_class in BUSINESS_FAULT


async def business_has_overdue_payout(db: AsyncSession, business_id: int) -> Payout | None:
    return await db.scalar(
        select(Payout)
        .where(
            Payout.payer_business_id == business_id,
            Payout.status == PayoutStatus.OVERDUE.value,
        )
        .order_by(Payout.due_at.asc())
    )


async def is_partner_traffic_suspended(db: AsyncSession, business_id: int) -> bool:
    row = await db.scalar(
        select(PartnerTrafficSuspension).where(
            PartnerTrafficSuspension.business_id == business_id,
            PartnerTrafficSuspension.active.is_(True),
        )
    )
    return row is not None


async def refresh_traffic_suspension(db: AsyncSession, business_id: int) -> None:
    overdue = await business_has_overdue_payout(db, business_id)
    current = await db.scalar(
        select(PartnerTrafficSuspension).where(PartnerTrafficSuspension.business_id == business_id)
    )
    if overdue:
        if current and current.active:
            current.payout_id = overdue.id
            return
        if current:
            current.active = True
            current.payout_id = overdue.id
            current.reason = "PAYOUT_OVERDUE"
            current.released_at = None
        else:
            db.add(
                PartnerTrafficSuspension(
                    business_id=business_id,
                    payout_id=overdue.id,
                    reason="PAYOUT_OVERDUE",
                    active=True,
                )
            )
        await record_audit(
            db,
            action="traffic.suspended",
            entity_type="business",
            entity_id=business_id,
            system_actor="scheduler",
            reason="PAYOUT_OVERDUE",
            new_status="suspended",
        )
        return
    if current and current.active:
        current.active = False
        current.released_at = datetime.now(timezone.utc)
        await record_audit(
            db,
            action="traffic.released",
            entity_type="business",
            entity_id=business_id,
            system_actor="scheduler",
            old_status="suspended",
            new_status="active",
        )


async def assert_partner_promotion_allowed(db: AsyncSession, business_id: int) -> None:
    from app.modules.finance.errors import fin_error

    if await is_partner_traffic_suspended(db, business_id):
        raise fin_error(
            "FIN_PARTNER_TRAFFIC_SUSPENDED",
            "Partner promotion for this business is temporarily suspended due to overdue payout",
            403,
        )
