from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    CommissionStatus,
    FinancialOperationType,
    FinancialScope,
    PayoutFailureClass,
    PayoutStatus,
    ProfileStatus,
)
from app.core.config import settings
from app.modules.businesses.models import Business
from app.modules.commissions.models import Commission
from app.modules.finance.audit import record_audit
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.errors import fin_error
from app.modules.finance.idempotency import claim_idempotency
from app.modules.finance.ledger import record_entry
from app.modules.finance.legal import require_verified_legal_entity
from app.modules.finance.metrics import inc
from app.modules.finance.models import LegalEntity, PartnerPayoutProfile
from app.modules.finance.money import as_money, as_utc, assert_positive, assert_rub
from app.modules.finance.providers.factory import get_payout_provider
from app.modules.finance.self_deal import assert_not_self_deal
from app.modules.finance.suspension import is_business_fault, refresh_traffic_suspension
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout, PayoutItem

OPEN_PAYOUT_STATUSES = {
    PayoutStatus.CREATED.value,
    PayoutStatus.AWAITING_CONFIRMATION.value,
    PayoutStatus.PROCESSING.value,
    PayoutStatus.OVERDUE.value,
    PayoutStatus.PENDING.value,
}
TERMINAL_PAYOUT_STATUSES = {
    PayoutStatus.PAID.value,
    PayoutStatus.CANCELLED.value,
}
AVAILABLE_COMMISSION = {CommissionStatus.AVAILABLE.value, CommissionStatus.PAYABLE.value}


def _min_amount() -> Decimal:
    return as_money(settings.PAYOUT_MIN_AMOUNT)


async def generate_due_payouts(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    ignore_interval: bool = False,
) -> list[Payout]:
    now = now or datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Commission.business_id, Commission.partner_id)
            .where(Commission.status.in_(tuple(AVAILABLE_COMMISSION)), Commission.active_payout_id.is_(None))
            .distinct()
        )
    ).all()
    created: list[Payout] = []
    for business_id, partner_id in rows:
        payout = await _generate_for_pair(db, business_id, partner_id, now=now, ignore_interval=ignore_interval)
        if payout:
            created.append(payout)
    return created


async def _generate_for_pair(
    db: AsyncSession,
    business_id: int,
    partner_id: int,
    *,
    now: datetime,
    ignore_interval: bool,
) -> Payout | None:
    open_existing = await db.scalar(
        select(Payout).where(
            Payout.payer_business_id == business_id,
            Payout.partner_id == partner_id,
            Payout.status.in_(tuple(OPEN_PAYOUT_STATUSES)),
        )
    )
    if open_existing:
        return None
    if not ignore_interval:
        last = (
            await db.execute(
                select(Payout)
                .where(Payout.payer_business_id == business_id, Payout.partner_id == partner_id)
                .order_by(Payout.created_at.desc())
            )
        ).scalars().first()
        last_at = as_utc(last.created_at) if last else None
        now_utc = as_utc(now)
        if last_at and now_utc and (now_utc - last_at) < timedelta(days=settings.PAYOUT_INTERVAL_DAYS):
            return None

    commissions = (
        await db.execute(
            select(Commission)
            .where(
                Commission.business_id == business_id,
                Commission.partner_id == partner_id,
                Commission.status.in_(tuple(AVAILABLE_COMMISSION)),
                Commission.active_payout_id.is_(None),
            )
            .with_for_update()
        )
    ).scalars().all()
    total = sum((as_money(item.amount) for item in commissions), Decimal("0.00"))
    if total < _min_amount() or not commissions:
        return None

    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner_id)
    key = f"payout-gen:{business_id}:{partner_id}:{now.date().isoformat()}"
    if not await claim_idempotency(db, key, "payout_generation", resource_type="payout_batch"):
        return None

    business = await db.scalar(select(Business).where(Business.id == business_id))
    partner = await db.scalar(select(PartnerProfile).where(PartnerProfile.id == partner_id))
    if not business or not partner:
        return None
    offer_ids = {item.offer_id for item in commissions if item.offer_id}
    for offer_id in offer_ids:
        offer = await db.scalar(select(Offer).where(Offer.id == offer_id))
        if offer:
            await assert_not_self_deal(db, offer=offer, partner_id=partner_id)

    if not eligibility.eligible:
        # Obligation is still created; sending is gated on confirm.
        pass

    payout = Payout(
        partner_id=partner_id,
        payer_business_id=business_id,
        payer_legal_entity_id=business.legal_entity_id,
        recipient_legal_entity_id=partner.legal_entity_id,
        amount=assert_positive(total),
        currency=assert_rub("RUB"),
        status=PayoutStatus.AWAITING_CONFIRMATION.value,
        provider="TBANK",
        idempotency_key=key,
        due_at=now + timedelta(days=settings.PAYOUT_DUE_DAYS),
        version=1,
    )
    db.add(payout)
    await db.flush()
    for commission in commissions:
        db.add(PayoutItem(payout_id=payout.id, commission_id=commission.id, amount=as_money(commission.amount)))
        commission.active_payout_id = payout.id
        commission.status = CommissionStatus.PAYOUT_PENDING.value
    inc("payout_created_total")
    await record_entry(
        db,
        scope=FinancialScope.PAYOUT,
        operation_type=FinancialOperationType.PAYOUT_CREATED,
        amount=payout.amount,
        currency="RUB",
        reference_type="payout",
        reference_id=payout.id,
        business_id=business_id,
        partner_id=partner_id,
        legal_entity_id=business.legal_entity_id,
    )
    await record_audit(
        db,
        action="payout.created",
        entity_type="payout",
        entity_id=payout.id,
        system_actor="scheduler",
        new_status=payout.status,
    )
    return payout


async def confirm_payout(
    db: AsyncSession,
    payout: Payout,
    *,
    actor_user_id: int | None,
) -> Payout:
    if payout.status in {PayoutStatus.PAID.value, PayoutStatus.PROCESSING.value}:
        return payout
    if payout.status not in {
        PayoutStatus.CREATED.value,
        PayoutStatus.AWAITING_CONFIRMATION.value,
        PayoutStatus.OVERDUE.value,
        PayoutStatus.PENDING.value,
        PayoutStatus.FAILED.value,
        PayoutStatus.MANUAL_REVIEW.value,
    }:
        raise fin_error("FIN_PAYOUT_ALREADY_PROCESSED", "Payout cannot be confirmed")

    payout.version = int(payout.version or 1) + 1
    await db.flush()

    if not payout.payer_business_id:
        raise fin_error("FIN_PAYOUT_INVALID", "Payout payer is missing")
    business = await db.scalar(select(Business).where(Business.id == payout.payer_business_id))
    if not business:
        raise fin_error("FIN_BUSINESS_NOT_FOUND", "Business not found", 404)
    payer_entity = await db.get(LegalEntity, business.legal_entity_id) if business.legal_entity_id else None
    require_verified_legal_entity(payer_entity)
    eligibility = await PartnerPayoutEligibilityService(db).check_payout_eligibility(payout.partner_id)
    if not eligibility.eligible:
        payout.status = PayoutStatus.MANUAL_REVIEW.value
        payout.failure_class = _eligibility_failure_class(eligibility.reason_code)
        payout.failure_message = eligibility.reason_message
        payout.failed_at = datetime.now(timezone.utc)
        await record_audit(
            db,
            action="payout.manual_review",
            entity_type="payout",
            entity_id=payout.id,
            actor_user_id=actor_user_id,
            old_status=PayoutStatus.AWAITING_CONFIRMATION.value,
            new_status=payout.status,
            reason=eligibility.reason_code,
        )
        raise fin_error("FIN_PARTNER_NOT_PAYOUT_ELIGIBLE", eligibility.reason_message or "Partner is not eligible")

    profile = await db.scalar(
        select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == payout.partner_id)
    )
    if not profile or profile.status != ProfileStatus.VERIFIED.value:
        raise fin_error("FIN_PAYOUT_PROFILE_REQUIRED", "Verified payout profile is required")

    confirm_key = f"payout-confirm:{payout.id}"
    if not await claim_idempotency(db, confirm_key, "payout_confirm", resource_type="payout", resource_id=payout.id):
        await db.refresh(payout)
        return payout

    payout.confirmed_at = datetime.now(timezone.utc)
    payout.status = PayoutStatus.PROCESSING.value
    payout.processing_at = payout.confirmed_at
    await record_entry(
        db,
        scope=FinancialScope.PAYOUT,
        operation_type=FinancialOperationType.PAYOUT_CONFIRMED,
        amount=payout.amount,
        currency="RUB",
        reference_type="payout",
        reference_id=payout.id,
        business_id=payout.payer_business_id,
        partner_id=payout.partner_id,
        legal_entity_id=payout.payer_legal_entity_id,
    )
    await record_audit(
        db,
        action="payout.confirmed",
        entity_type="payout",
        entity_id=payout.id,
        actor_user_id=actor_user_id,
        old_status=PayoutStatus.AWAITING_CONFIRMATION.value,
        new_status=payout.status,
        metadata={"live": settings.live_financial_transactions_allowed},
    )

    provider = get_payout_provider(db)
    result = await provider.create_payout(
        amount=as_money(payout.amount),
        currency="RUB",
        order_id=f"payout-{payout.id}",
        recipient={
            "CardId": profile.provider_recipient_id,
            "account": None,
            "bank_bik": None,
        },
        description=f"RefIQ partner payout {payout.id}",
    )
    payout.provider = result.provider
    payout.provider_transaction_id = result.provider_transaction_id
    payout.provider_status = result.raw_status or result.provider_status
    if result.ok:
        await record_entry(
            db,
            scope=FinancialScope.PAYOUT,
            operation_type=FinancialOperationType.PAYOUT_PROCESSING,
            amount=payout.amount,
            currency="RUB",
            reference_type="payout",
            reference_id=payout.id,
            business_id=payout.payer_business_id,
            partner_id=payout.partner_id,
        )
        if result.provider_status == PayoutStatus.PAID.value:
            await mark_payout_paid(db, payout)
    else:
        await mark_payout_failed(
            db,
            payout,
            failure_class=PayoutFailureClass.PROVIDER_ERROR.value,
            message=result.error_message,
        )
    return payout


async def mark_payout_paid(db: AsyncSession, payout: Payout) -> None:
    if payout.status == PayoutStatus.PAID.value:
        return
    old = payout.status
    payout.status = PayoutStatus.PAID.value
    payout.paid_at = datetime.now(timezone.utc)
    payout.processed_at = payout.paid_at
    items = (
        await db.execute(select(PayoutItem).where(PayoutItem.payout_id == payout.id))
    ).scalars().all()
    commission_ids = [item.commission_id for item in items]
    if commission_ids:
        commissions = (
            await db.execute(select(Commission).where(Commission.id.in_(commission_ids)))
        ).scalars().all()
        for commission in commissions:
            commission.status = CommissionStatus.PAID.value
    inc("payout_paid_total")
    await record_entry(
        db,
        scope=FinancialScope.PAYOUT,
        operation_type=FinancialOperationType.PAYOUT_PAID,
        amount=payout.amount,
        currency="RUB",
        reference_type="payout",
        reference_id=payout.id,
        business_id=payout.payer_business_id,
        partner_id=payout.partner_id,
        legal_entity_id=payout.payer_legal_entity_id,
    )
    await record_audit(
        db,
        action="payout.paid",
        entity_type="payout",
        entity_id=payout.id,
        system_actor="provider",
        old_status=old,
        new_status=payout.status,
    )
    if payout.payer_business_id:
        await refresh_traffic_suspension(db, payout.payer_business_id)


async def mark_payout_failed(
    db: AsyncSession,
    payout: Payout,
    *,
    failure_class: str,
    message: str | None = None,
) -> None:
    if payout.status == PayoutStatus.PAID.value:
        return
    old = payout.status
    payout.failure_class = failure_class
    payout.failure_message = (message or "")[:500] or None
    payout.failed_at = datetime.now(timezone.utc)
    if is_business_fault(failure_class):
        payout.status = PayoutStatus.FAILED.value
    else:
        payout.status = PayoutStatus.MANUAL_REVIEW.value
        await _release_commissions(db, payout)
    inc("payout_failed_total")
    inc("financial_provider_error_total")
    await record_entry(
        db,
        scope=FinancialScope.PAYOUT,
        operation_type=FinancialOperationType.PAYOUT_FAILED,
        amount=payout.amount,
        currency="RUB",
        reference_type="payout",
        reference_id=payout.id,
        business_id=payout.payer_business_id,
        partner_id=payout.partner_id,
        metadata={"failure_class": failure_class},
    )
    await record_audit(
        db,
        action="payout.failed",
        entity_type="payout",
        entity_id=payout.id,
        system_actor="provider",
        old_status=old,
        new_status=payout.status,
        reason=failure_class,
    )
    if payout.payer_business_id:
        await refresh_traffic_suspension(db, payout.payer_business_id)


async def mark_overdue_payouts(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Payout).where(
                Payout.status.in_(
                    [
                        PayoutStatus.CREATED.value,
                        PayoutStatus.AWAITING_CONFIRMATION.value,
                        PayoutStatus.PENDING.value,
                    ]
                ),
                Payout.due_at.is_not(None),
                Payout.due_at < now,
            )
        )
    ).scalars().all()
    count = 0
    for payout in rows:
        payout.status = PayoutStatus.OVERDUE.value
        count += 1
        inc("payout_overdue_total")
        await record_entry(
            db,
            scope=FinancialScope.PAYOUT,
            operation_type=FinancialOperationType.PAYOUT_OVERDUE,
            amount=payout.amount,
            currency="RUB",
            reference_type="payout",
            reference_id=payout.id,
            business_id=payout.payer_business_id,
            partner_id=payout.partner_id,
        )
        await record_audit(
            db,
            action="payout.overdue",
            entity_type="payout",
            entity_id=payout.id,
            system_actor="scheduler",
            new_status=PayoutStatus.OVERDUE.value,
        )
        if payout.payer_business_id:
            await refresh_traffic_suspension(db, payout.payer_business_id)
    return count


async def _release_commissions(db: AsyncSession, payout: Payout) -> None:
    items = (await db.execute(select(PayoutItem).where(PayoutItem.payout_id == payout.id))).scalars().all()
    ids = [item.commission_id for item in items]
    if not ids:
        return
    commissions = (await db.execute(select(Commission).where(Commission.id.in_(ids)))).scalars().all()
    for commission in commissions:
        if commission.status == CommissionStatus.PAYOUT_PENDING.value:
            commission.status = CommissionStatus.AVAILABLE.value
            commission.active_payout_id = None


def _eligibility_failure_class(code: str | None) -> str:
    mapping = {
        "NPD_STATUS_INVALID": PayoutFailureClass.PARTNER_NPD_INVALID.value,
        "UNSUPPORTED_PARTNER_TYPE": PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value,
        "LEGAL_ENTITY_MISSING": PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value,
        "LEGAL_ENTITY_NOT_VERIFIED": PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value,
        "PAYOUT_PROFILE_MISSING": PayoutFailureClass.PARTNER_PAYMENT_DETAILS_INVALID.value,
        "PAYOUT_PROFILE_NOT_VERIFIED": PayoutFailureClass.PARTNER_PAYMENT_DETAILS_INVALID.value,
        "PAYMENT_DETAILS_INVALID": PayoutFailureClass.PARTNER_PAYMENT_DETAILS_INVALID.value,
        "PARTNER_BLOCKED": PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value,
    }
    return mapping.get(code or "", PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value)


def serialize_payout(payout: Payout, *, partner_name: str | None = None) -> dict:
    return {
        "id": payout.id,
        "payer_business_id": payout.payer_business_id,
        "payer_legal_entity_id": payout.payer_legal_entity_id,
        "recipient_partner_id": payout.partner_id,
        "recipient_legal_entity_id": payout.recipient_legal_entity_id,
        "partner_id": payout.partner_id,
        "partner_name": partner_name,
        "amount": float(as_money(payout.amount)),
        "currency": payout.currency,
        "status": payout.status,
        "provider": payout.provider,
        "provider_transaction_id": payout.provider_transaction_id,
        "provider_status": payout.provider_status,
        "failure_class": payout.failure_class,
        "due_at": payout.due_at.isoformat() if payout.due_at else None,
        "created_at": payout.created_at.isoformat() if payout.created_at else None,
        "confirmed_at": payout.confirmed_at.isoformat() if payout.confirmed_at else None,
        "processing_at": payout.processing_at.isoformat() if payout.processing_at else None,
        "paid_at": payout.paid_at.isoformat() if payout.paid_at else None,
        "failed_at": payout.failed_at.isoformat() if payout.failed_at else None,
    }
