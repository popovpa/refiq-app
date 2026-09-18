from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import PayoutStatus
from app.modules.billing.models import BillingTransaction
from app.modules.finance.billing import apply_payment_status
from app.modules.finance.metrics import inc
from app.modules.finance.payouts import mark_payout_failed, mark_payout_paid
from app.modules.finance.providers.factory import get_payment_provider, get_payout_provider
from app.modules.finance.providers.mapping import INTERNAL_PAYMENT_FAILED, INTERNAL_PAYMENT_SUCCEEDED
from app.modules.payouts.models import Payout
from app.common.enums import PayoutFailureClass


async def reconcile_open_transactions(db: AsyncSession, *, now=None) -> int:
    changed = 0
    payment_provider = get_payment_provider(db)
    payout_provider = get_payout_provider(db)

    payments = (
        await db.execute(
            select(BillingTransaction).where(
                BillingTransaction.status.in_(["created", "processing"]),
                BillingTransaction.provider_transaction_id.is_not(None),
            )
        )
    ).scalars().all()
    for tx in payments:
        result = await payment_provider.get_payment_status(tx.provider_transaction_id)
        if not result.ok:
            inc("financial_reconciliation_mismatch_total")
            continue
        before = tx.status
        await apply_payment_status(db, tx, result.provider_status or "", result.raw_status)
        if tx.status != before:
            changed += 1
        if result.provider_status == INTERNAL_PAYMENT_SUCCEEDED and before in {"succeeded", "paid"}:
            continue
        if result.provider_status not in {INTERNAL_PAYMENT_SUCCEEDED, INTERNAL_PAYMENT_FAILED, "PAYMENT_PROCESSING"}:
            inc("financial_reconciliation_mismatch_total")

    payouts = (
        await db.execute(
            select(Payout).where(
                Payout.status.in_([PayoutStatus.PROCESSING.value, PayoutStatus.RECONCILIATION_REQUIRED.value]),
                Payout.provider_transaction_id.is_not(None),
            )
        )
    ).scalars().all()
    for payout in payouts:
        result = await payout_provider.get_payout_status(payout.provider_transaction_id)
        if not result.ok:
            payout.status = PayoutStatus.RECONCILIATION_REQUIRED.value
            inc("financial_reconciliation_mismatch_total")
            continue
        if result.provider_status == PayoutStatus.PAID.value:
            await mark_payout_paid(db, payout)
            changed += 1
        elif result.provider_status == PayoutStatus.FAILED.value:
            await mark_payout_failed(
                db,
                payout,
                failure_class=PayoutFailureClass.PROVIDER_ERROR.value,
                message=result.error_message,
            )
            changed += 1
    return changed
