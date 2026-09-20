from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CommissionStatus, PayoutStatus
from app.modules.commissions.models import Commission
from app.modules.finance.audit import record_audit
from app.modules.finance.commission import cancel_self_promotion_commission
from app.modules.finance.payouts import sanitize_payout_self_deal
from app.modules.finance.self_deal import SELF_PROMOTION_INVALID, check_self_deal
from app.modules.offers.models import Offer
from app.modules.payouts.models import Payout, PayoutItem


OPEN_PAYOUTS = {
    PayoutStatus.CREATED.value,
    PayoutStatus.AWAITING_CONFIRMATION.value,
    PayoutStatus.PROCESSING.value,
    PayoutStatus.OVERDUE.value,
    PayoutStatus.PENDING.value,
    PayoutStatus.FAILED.value,
    PayoutStatus.MANUAL_REVIEW.value,
}


def _empty_report() -> dict:
    return {
        "dry_run": True,
        "invalid_commissions": 0,
        "invalid_payout_items": 0,
        "invalid_payouts": 0,
        "paid_review_payouts": 0,
        "commission_amount": "0.00",
        "payout_amount": "0.00",
        "commission_ids": [],
        "payout_ids": [],
        "paid_payout_ids": [],
        "actions": [],
    }


async def find_self_promotion_violations(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Commission))).scalars().all()
    found: list[dict] = []
    for commission in rows:
        offer = await db.scalar(select(Offer).where(Offer.id == commission.offer_id)) if commission.offer_id else None
        decision = await check_self_deal(
            db,
            partner_id=commission.partner_id,
            offer=offer,
            business_id=commission.business_id,
        )
        if decision.allowed:
            continue
        found.append(
            {
                "commission_id": commission.id,
                "status": commission.status,
                "amount": str(commission.amount),
                "business_id": commission.business_id,
                "partner_id": commission.partner_id,
                "offer_id": commission.offer_id,
                "conversion_id": commission.conversion_id,
                "active_payout_id": commission.active_payout_id,
                "reason_code": decision.reason_code,
            }
        )
    return found


async def repair_self_promotion(db: AsyncSession, *, execute: bool = False) -> dict:
    """Default is dry-run. Pass execute=True to cancel unpaid self-deal commissions
    and sanitize unpaid payouts. Paid payouts are never clawed back.
    """
    violations = await find_self_promotion_violations(db)
    report = _empty_report()
    report["dry_run"] = not execute
    report["invalid_commissions"] = len(violations)
    report["commission_ids"] = [item["commission_id"] for item in violations]
    report["commission_amount"] = str(sum((Decimal(item["amount"]) for item in violations), Decimal("0.00")))
    payout_ids = {item["active_payout_id"] for item in violations if item["active_payout_id"]}
    extra_items = (
        await db.execute(
            select(PayoutItem).where(PayoutItem.commission_id.in_(report["commission_ids"] or [0]))
        )
    ).scalars().all()
    report["invalid_payout_items"] = len(extra_items)
    for item in extra_items:
        payout_ids.add(item.payout_id)
    report["payout_ids"] = sorted(pid for pid in payout_ids if pid)

    paid_ids = []
    open_ids = []
    payout_amount = Decimal("0.00")
    for payout_id in report["payout_ids"]:
        payout = await db.get(Payout, payout_id)
        if not payout:
            continue
        payout_amount += Decimal(str(payout.amount))
        if payout.status == PayoutStatus.PAID.value:
            paid_ids.append(payout.id)
        elif payout.status in OPEN_PAYOUTS or payout.status == PayoutStatus.CANCELLED.value:
            open_ids.append(payout.id)
    report["invalid_payouts"] = len(report["payout_ids"])
    report["paid_review_payouts"] = len(paid_ids)
    report["paid_payout_ids"] = paid_ids
    report["payout_amount"] = str(payout_amount)

    if not execute:
        report["actions"] = [
            {
                "commission_id": item["commission_id"],
                "status": item["status"],
                "reason_code": item["reason_code"],
                "planned": "review" if item["status"] == CommissionStatus.PAID.value else "cancel",
            }
            for item in violations
        ]
        return report

    for item in violations:
        commission = await db.get(Commission, item["commission_id"])
        if not commission:
            continue
        result = await cancel_self_promotion_commission(
            db,
            commission,
            reason_code=item["reason_code"] or SELF_PROMOTION_INVALID,
        )
        report["actions"].append(
            {"commission_id": commission.id, "result": result, "reason_code": item["reason_code"]}
        )

    for payout_id in open_ids:
        payout = await db.get(Payout, payout_id)
        if not payout or payout.status == PayoutStatus.PAID.value:
            continue
        await sanitize_payout_self_deal(db, payout, system_actor="repair_self_promotion")

    for payout_id in paid_ids:
        payout = await db.get(Payout, payout_id)
        if not payout:
            continue
        await record_audit(
            db,
            action="SELF_PROMOTION_INVALID_AFTER_PAYOUT",
            entity_type="payout",
            entity_id=payout.id,
            system_actor="repair_self_promotion",
            old_status=payout.status,
            reason=SELF_PROMOTION_INVALID,
            metadata={
                "payout_id": payout.id,
                "business_id": payout.payer_business_id,
                "partner_id": payout.partner_id,
                "amount": str(payout.amount),
                "auto_clawback": False,
            },
        )
    return report


async def _cli() -> None:
    parser = argparse.ArgumentParser(description="Repair self-promotion commissions and payouts")
    parser.add_argument("--execute", action="store_true", help="Apply corrections (default is dry-run)")
    args = parser.parse_args()
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        report = await repair_self_promotion(db, execute=args.execute)
        if args.execute:
            await db.commit()
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_cli())

