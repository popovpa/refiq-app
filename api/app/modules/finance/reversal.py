from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    CommissionStatus,
    ConversionReversalReason,
    ConversionStatus,
    FinancialOperationType,
    FinancialScope,
)
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.finance.audit import record_audit
from app.modules.finance.errors import fin_error
from app.modules.finance.ledger import record_entry
from app.modules.finance.money import as_money

PAID_COMMISSION = {CommissionStatus.PAID.value, CommissionStatus.PAYOUT_PENDING.value}


async def reverse_conversion(
    db: AsyncSession,
    conversion: Conversion,
    *,
    reason: str,
    comment: str | None = None,
    actor_user_id: int | None = None,
    system_actor: str | None = None,
) -> dict:
    if conversion.status == ConversionStatus.REVERSED.value:
        return {"status": "already_reversed", "manual_review": False}
    try:
        ConversionReversalReason(reason)
    except ValueError as exc:
        raise fin_error("FIN_REVERSAL_REASON_INVALID", "Unknown reversal reason") from exc
    if conversion.status not in {
        ConversionStatus.PENDING.value,
        ConversionStatus.APPROVED.value,
        ConversionStatus.PAID.value,
    }:
        raise fin_error("FIN_CONVERSION_NOT_REVERSIBLE", "Conversion cannot be reversed")

    now = datetime.now(timezone.utc)
    old_status = conversion.status
    conversion.status = ConversionStatus.REVERSED.value
    conversion.reversed_at = now
    conversion.reversed_by_user_id = actor_user_id
    conversion.reversal_reason = reason
    conversion.reversal_comment = (comment or "")[:1000] or None

    commission = await db.scalar(select(Commission).where(Commission.conversion_id == conversion.id))
    manual_review = False
    if commission:
        if commission.status in PAID_COMMISSION or commission.status == CommissionStatus.PAID.value:
            manual_review = True
            await record_entry(
                db,
                scope=FinancialScope.PARTNER_COMMISSION,
                operation_type=FinancialOperationType.COMMISSION_REVERSED,
                amount=as_money(commission.amount),
                currency=commission.currency,
                reference_type="commission",
                reference_id=commission.id,
                business_id=commission.business_id,
                partner_id=commission.partner_id,
                legal_entity_id=commission.partner_legal_entity_id,
                metadata={"kind": "REVERSED_AFTER_PAYOUT", "auto_clawback": False},
            )
            await record_audit(
                db,
                action="commission.reversed_after_payout",
                entity_type="commission",
                entity_id=commission.id,
                actor_user_id=actor_user_id,
                system_actor=system_actor,
                old_status=commission.status,
                new_status=commission.status,
                reason="REVERSED_AFTER_PAYOUT",
            )
        else:
            old = commission.status
            commission.status = CommissionStatus.REVERSED.value
            commission.reversed_at = now
            await record_entry(
                db,
                scope=FinancialScope.PARTNER_COMMISSION,
                operation_type=FinancialOperationType.COMMISSION_REVERSED,
                amount=as_money(commission.amount),
                currency=commission.currency,
                reference_type="commission",
                reference_id=commission.id,
                business_id=commission.business_id,
                partner_id=commission.partner_id,
                legal_entity_id=commission.partner_legal_entity_id,
                metadata={"kind": "REVERSED_UNPAID"},
            )
            await record_audit(
                db,
                action="commission.reversed",
                entity_type="commission",
                entity_id=commission.id,
                actor_user_id=actor_user_id,
                system_actor=system_actor,
                old_status=old,
                new_status=CommissionStatus.REVERSED.value,
                reason=reason,
            )
    await record_audit(
        db,
        action="conversion.reversed",
        entity_type="conversion",
        entity_id=conversion.id,
        actor_user_id=actor_user_id,
        system_actor=system_actor,
        old_status=old_status,
        new_status=ConversionStatus.REVERSED.value,
        reason=reason,
        metadata={"comment": comment} if comment else None,
    )
    return {"status": "reversed", "manual_review": manual_review}
