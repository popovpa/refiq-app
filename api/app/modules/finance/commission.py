from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    CommissionStatus,
    CommissionType,
    ConversionStatus,
    FinancialOperationType,
    FinancialScope,
)
from app.modules.businesses.models import Business
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.finance.audit import record_audit
from app.modules.finance.errors import fin_error
from app.modules.finance.ledger import record_entry
from app.modules.finance.metrics import inc
from app.modules.finance.money import as_money, assert_positive, assert_rub
from app.modules.finance.self_deal import assert_not_self_deal
from app.modules.offers.models import Offer, OfferCommissionRule
from app.modules.partners.models import PartnerProfile

AVAILABLE_STATUSES = {CommissionStatus.AVAILABLE.value, CommissionStatus.PAYABLE.value}
HOLD_STATUSES = {CommissionStatus.HOLD.value, CommissionStatus.APPROVED.value}
UNPAID_STATUSES = {
    CommissionStatus.PENDING.value,
    CommissionStatus.HOLD.value,
    CommissionStatus.APPROVED.value,
    CommissionStatus.AVAILABLE.value,
    CommissionStatus.PAYABLE.value,
}


def normalize_commission_status(status: str | None) -> str:
    if status in {CommissionStatus.APPROVED.value}:
        return CommissionStatus.HOLD.value
    if status in {CommissionStatus.PAYABLE.value}:
        return CommissionStatus.AVAILABLE.value
    return status or CommissionStatus.PENDING.value


def snapshot_rule(offer: Offer) -> OfferCommissionRule | None:
    return offer.commission_rules[0] if offer.commission_rules else None


def calculate_commission_amount(rule: OfferCommissionRule | None, base: Decimal) -> Decimal:
    if rule is None:
        return as_money("0")
    value = as_money(rule.value)
    if rule.type == CommissionType.PERCENT.value:
        return as_money((base * value) / Decimal("100"))
    return value


async def create_commission_for_approved_conversion(
    db: AsyncSession,
    conversion: Conversion,
    *,
    actor_user_id: int | None = None,
) -> Commission | None:
    if conversion.partner_id is None:
        return None
    existing = await db.scalar(select(Commission).where(Commission.conversion_id == conversion.id))
    if existing:
        return existing

    offer = await db.scalar(select(Offer).where(Offer.id == conversion.offer_id))
    if not offer:
        raise fin_error("FIN_OFFER_NOT_FOUND", "Offer not found", 404)
    await assert_not_self_deal(db, offer=offer, partner_id=conversion.partner_id)

    currency = assert_rub(conversion.currency)
    amount = as_money(conversion.commission_amount)
    if amount <= 0:
        return None
    assert_positive(amount)

    business = await db.scalar(select(Business).where(Business.id == conversion.business_id))
    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.id == conversion.partner_id))
    rule = snapshot_rule(offer) if offer else None
    hold_days = int(conversion.hold_period_days_snapshot or (offer.hold_period_days if offer else 0) or 0)
    approved_at = conversion.approved_at or datetime.now(timezone.utc)
    available_at = approved_at + timedelta(days=hold_days)
    status = CommissionStatus.AVAILABLE.value if hold_days == 0 else CommissionStatus.HOLD.value
    if hold_days == 0:
        available_at = approved_at

    commission = Commission(
        conversion_id=conversion.id,
        offer_id=conversion.offer_id,
        business_id=conversion.business_id,
        partner_id=conversion.partner_id,
        business_legal_entity_id=business.legal_entity_id if business else None,
        partner_legal_entity_id=partner.legal_entity_id if partner else None,
        amount=amount,
        currency=currency,
        status=status,
        commission_type=rule.type if rule else None,
        commission_value=as_money(rule.value) if rule else None,
        calculation_base=as_money(conversion.amount),
        calculation_version="v1",
        offer_terms_version=int(offer.terms_version or 1) if offer else 1,
        hold_period_days=hold_days,
        available_at=available_at,
    )
    db.add(commission)
    await db.flush()
    inc("commission_created_total")
    await record_entry(
        db,
        scope=FinancialScope.PARTNER_COMMISSION,
        operation_type=FinancialOperationType.COMMISSION_CREATED,
        amount=amount,
        currency=currency,
        reference_type="commission",
        reference_id=commission.id,
        business_id=commission.business_id,
        partner_id=commission.partner_id,
        legal_entity_id=commission.partner_legal_entity_id,
    )
    await record_audit(
        db,
        action="commission.created",
        entity_type="commission",
        entity_id=commission.id,
        actor_user_id=actor_user_id,
        system_actor=None if actor_user_id else "system",
        new_status=status,
    )
    if status == CommissionStatus.HOLD.value:
        inc("commission_hold_total")
        await record_entry(
            db,
            scope=FinancialScope.PARTNER_COMMISSION,
            operation_type=FinancialOperationType.COMMISSION_HOLD_STARTED,
            amount=amount,
            currency=currency,
            reference_type="commission",
            reference_id=commission.id,
            business_id=commission.business_id,
            partner_id=commission.partner_id,
            legal_entity_id=commission.partner_legal_entity_id,
        )
    else:
        inc("commission_available_total")
        await record_entry(
            db,
            scope=FinancialScope.PARTNER_COMMISSION,
            operation_type=FinancialOperationType.COMMISSION_AVAILABLE,
            amount=amount,
            currency=currency,
            reference_type="commission",
            reference_id=commission.id,
            business_id=commission.business_id,
            partner_id=commission.partner_id,
            legal_entity_id=commission.partner_legal_entity_id,
        )
    return commission


async def release_due_holds(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Commission).where(
                Commission.status.in_(tuple(HOLD_STATUSES)),
                Commission.available_at.is_not(None),
                Commission.available_at <= now,
            )
        )
    ).scalars().all()
    released = 0
    for commission in rows:
        old = commission.status
        commission.status = CommissionStatus.AVAILABLE.value
        released += 1
        inc("commission_available_total")
        await record_entry(
            db,
            scope=FinancialScope.PARTNER_COMMISSION,
            operation_type=FinancialOperationType.COMMISSION_AVAILABLE,
            amount=commission.amount,
            currency=commission.currency,
            reference_type="commission",
            reference_id=commission.id,
            business_id=commission.business_id,
            partner_id=commission.partner_id,
            legal_entity_id=commission.partner_legal_entity_id,
        )
        await record_audit(
            db,
            action="commission.available",
            entity_type="commission",
            entity_id=commission.id,
            system_actor="scheduler",
            old_status=old,
            new_status=CommissionStatus.AVAILABLE.value,
        )
    return released


async def earnings_breakdown(db: AsyncSession, *, partner_id: int | None = None, business_id: int | None = None) -> dict:
    query = select(Commission)
    if partner_id is not None:
        query = query.where(Commission.partner_id == partner_id)
    if business_id is not None:
        query = query.where(Commission.business_id == business_id)
    rows = (await db.execute(query)).scalars().all()
    totals = {
        "pending": Decimal("0.00"),
        "hold": Decimal("0.00"),
        "available": Decimal("0.00"),
        "payout_pending": Decimal("0.00"),
        "paid": Decimal("0.00"),
        "reversed": Decimal("0.00"),
        "cancelled": Decimal("0.00"),
        "currency": "RUB",
    }
    for item in rows:
        amount = as_money(item.amount)
        status = normalize_commission_status(item.status)
        if status == CommissionStatus.PENDING.value:
            totals["pending"] += amount
        elif status in HOLD_STATUSES:
            totals["hold"] += amount
        elif status in AVAILABLE_STATUSES:
            totals["available"] += amount
        elif status == CommissionStatus.PAYOUT_PENDING.value:
            totals["payout_pending"] += amount
        elif status == CommissionStatus.PAID.value:
            totals["paid"] += amount
        elif status == CommissionStatus.REVERSED.value:
            totals["reversed"] += amount
        elif status == CommissionStatus.CANCELLED.value:
            totals["cancelled"] += amount
    return {key: (float(value) if key != "currency" else value) for key, value in totals.items()}
