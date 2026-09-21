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
from app.modules.conversions.models import Conversion
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
from app.modules.finance.commission import cancel_self_promotion_commission
from app.modules.finance.self_deal import (
    PAYOUT_SELF_DEAL_FORBIDDEN,
    SELF_PROMOTION_INVALID,
    check_self_deal,
)
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
    eligible_commissions: list[Commission] = []
    for commission in commissions:
        offer = await db.scalar(select(Offer).where(Offer.id == commission.offer_id)) if commission.offer_id else None
        decision = await check_self_deal(
            db,
            partner_id=partner_id,
            offer=offer,
            business_id=business_id,
        )
        if not decision.allowed:
            await cancel_self_promotion_commission(
                db,
                commission,
                reason_code=decision.reason_code or PAYOUT_SELF_DEAL_FORBIDDEN,
            )
            continue
        eligible_commissions.append(commission)
    commissions = eligible_commissions
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

    if not eligibility.eligible:
        # Obligation is still created; sending is gated on confirm.
        pass

    profile = await db.scalar(
        select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner_id)
    )
    payout = Payout(
        partner_id=partner_id,
        payout_profile_id=profile.id if profile else None,
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
    await sanitize_payout_self_deal(db, payout, actor_user_id=actor_user_id)
    if payout.status == PayoutStatus.CANCELLED.value:
        raise fin_error(PAYOUT_SELF_DEAL_FORBIDDEN, "Payout cancelled: self-promotion items only")
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
    payout.payout_profile_id = profile.id

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
    commission_ids = [item.commission_id for item in items if not item.excluded_reason]
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


async def sanitize_payout_self_deal(
    db: AsyncSession,
    payout: Payout,
    *,
    actor_user_id: int | None = None,
    system_actor: str | None = "system",
) -> Payout:
    """Drop self-deal items from an unpaid payout and cancel it if nothing remains."""
    if payout.status == PayoutStatus.PAID.value:
        return payout
    items = (await db.execute(select(PayoutItem).where(PayoutItem.payout_id == payout.id))).scalars().all()
    remaining: list[PayoutItem] = []
    removed = 0
    for item in items:
        if item.excluded_reason:
            continue
        commission = await db.get(Commission, item.commission_id)
        if not commission:
            remaining.append(item)
            continue
        offer = await db.scalar(select(Offer).where(Offer.id == commission.offer_id)) if commission.offer_id else None
        decision = await check_self_deal(
            db,
            partner_id=payout.partner_id,
            offer=offer,
            business_id=payout.payer_business_id,
        )
        if decision.allowed:
            remaining.append(item)
            continue
        item.excluded_reason = SELF_PROMOTION_INVALID
        removed += 1
        await cancel_self_promotion_commission(
            db,
            commission,
            reason_code=decision.reason_code or PAYOUT_SELF_DEAL_FORBIDDEN,
            actor_user_id=actor_user_id,
            system_actor=system_actor,
        )
        await record_audit(
            db,
            action="PAYOUT_ITEM_REMOVED_SELF_PROMOTION",
            entity_type="payout_item",
            entity_id=item.id,
            actor_user_id=actor_user_id,
            system_actor=system_actor,
            reason=decision.reason_code,
            metadata={
                "payout_id": payout.id,
                "commission_id": commission.id,
                "business_id": payout.payer_business_id,
                "partner_id": payout.partner_id,
                "offer_id": commission.offer_id,
            },
        )
    if not removed:
        return payout
    old_amount = payout.amount
    new_total = sum((as_money(item.amount) for item in remaining), Decimal("0.00"))
    old_status = payout.status
    if not remaining or new_total <= 0:
        payout.status = PayoutStatus.CANCELLED.value
        payout.failure_class = PayoutFailureClass.PARTNER_NOT_ELIGIBLE.value
        payout.failure_message = SELF_PROMOTION_INVALID
        await record_audit(
            db,
            action="payout.cancelled",
            entity_type="payout",
            entity_id=payout.id,
            actor_user_id=actor_user_id,
            system_actor=system_actor,
            old_status=old_status,
            new_status=payout.status,
            reason=SELF_PROMOTION_INVALID,
            metadata={"previous_amount": str(old_amount), "removed_items": removed},
        )
        return payout
    payout.amount = as_money(new_total)
    payout.version = int(payout.version or 1) + 1
    await record_audit(
        db,
        action="payout.recalculated",
        entity_type="payout",
        entity_id=payout.id,
        actor_user_id=actor_user_id,
        system_actor=system_actor,
        reason=SELF_PROMOTION_INVALID,
        metadata={"previous_amount": str(old_amount), "amount": str(payout.amount), "removed_items": removed},
    )
    return payout


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


def serialize_payout(
    payout: Payout,
    *,
    partner_name: str | None = None,
    business_name: str | None = None,
    commissions: list[dict] | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> dict:
    payload = {
        "id": payout.id,
        "payer_business_id": payout.payer_business_id,
        "payer_legal_entity_id": payout.payer_legal_entity_id,
        "recipient_partner_id": payout.partner_id,
        "recipient_legal_entity_id": payout.recipient_legal_entity_id,
        "payout_profile_id": payout.payout_profile_id,
        "partner_id": payout.partner_id,
        "partner_name": partner_name,
        "business": {
            "id": payout.payer_business_id,
            "name": business_name,
        },
        "amount": float(as_money(payout.amount)),
        "currency": payout.currency,
        "status": payout.status,
        "provider": payout.provider,
        "provider_transaction_id": payout.provider_transaction_id,
        "provider_status": payout.provider_status,
        "failure_class": payout.failure_class,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "due_at": payout.due_at.isoformat() if payout.due_at else None,
        "created_at": payout.created_at.isoformat() if payout.created_at else None,
        "confirmed_at": payout.confirmed_at.isoformat() if payout.confirmed_at else None,
        "processing_at": payout.processing_at.isoformat() if payout.processing_at else None,
        "paid_at": payout.paid_at.isoformat() if payout.paid_at else None,
        "failed_at": payout.failed_at.isoformat() if payout.failed_at else None,
    }
    if commissions is not None:
        payload["commissions"] = commissions
    return payload


def _conversion_timestamp(conversion) -> datetime | None:
    return conversion.converted_at or conversion.created_at


def serialize_payout_commission_row(
    item: PayoutItem,
    *,
    commission: Commission | None,
    conversion,
    offer: Offer | None,
) -> dict:
    stamp = _conversion_timestamp(conversion) if conversion else None
    return {
        "id": commission.id if commission else item.commission_id,
        "amount": float(as_money(item.amount)),
        "currency": (commission.currency if commission else None) or "RUB",
        "conversion": {
            "id": conversion.id if conversion else (commission.conversion_id if commission else None),
            "created_at": stamp.isoformat() if stamp else None,
            "amount": float(conversion.amount) if conversion and conversion.amount is not None else None,
            "offer": {
                "id": offer.id if offer else (commission.offer_id if commission else None),
                "name": offer.name if offer else None,
            },
        },
    }


async def serialize_partner_payouts(db: AsyncSession, payouts: list[Payout]) -> list[dict]:
    """Partner-facing payout list with business name and included commissions."""
    if not payouts:
        return []

    business_ids = {p.payer_business_id for p in payouts if p.payer_business_id}
    businesses: dict[int, Business] = {}
    if business_ids:
        rows = (
            await db.execute(select(Business).where(Business.id.in_(business_ids)))
        ).scalars().all()
        businesses = {row.id: row for row in rows}

    included_items = [
        item
        for payout in payouts
        for item in (payout.items or [])
        if not item.excluded_reason
    ]
    commission_ids = [item.commission_id for item in included_items]
    commissions: dict[int, Commission] = {}
    if commission_ids:
        commission_rows = (
            await db.execute(select(Commission).where(Commission.id.in_(commission_ids)))
        ).scalars().all()
        commissions = {row.id: row for row in commission_rows}

    conversion_ids = {c.conversion_id for c in commissions.values() if c.conversion_id}
    conversions: dict[int, Conversion] = {}
    if conversion_ids:
        conversion_rows = (
            await db.execute(select(Conversion).where(Conversion.id.in_(conversion_ids)))
        ).scalars().all()
        conversions = {row.id: row for row in conversion_rows}

    offer_ids = {c.offer_id for c in commissions.values() if c.offer_id}
    for conversion in conversions.values():
        if conversion.offer_id:
            offer_ids.add(conversion.offer_id)
    offers: dict[int, Offer] = {}
    if offer_ids:
        offer_rows = (await db.execute(select(Offer).where(Offer.id.in_(offer_ids)))).scalars().all()
        offers = {row.id: row for row in offer_rows}

    result: list[dict] = []
    for payout in payouts:
        business = businesses.get(payout.payer_business_id) if payout.payer_business_id else None
        commission_rows: list[dict] = []
        period_stamps: list[datetime] = []
        for item in payout.items or []:
            if item.excluded_reason:
                continue
            commission = commissions.get(item.commission_id)
            conversion = conversions.get(commission.conversion_id) if commission else None
            offer = None
            if conversion and conversion.offer_id:
                offer = offers.get(conversion.offer_id)
            elif commission and commission.offer_id:
                offer = offers.get(commission.offer_id)
            row = serialize_payout_commission_row(
                item, commission=commission, conversion=conversion, offer=offer
            )
            commission_rows.append(row)
            stamp = _conversion_timestamp(conversion) if conversion else None
            if stamp:
                period_stamps.append(stamp)
        commission_rows.sort(
            key=lambda row: row["conversion"]["created_at"] or "",
            reverse=True,
        )
        period_start = min(period_stamps) if period_stamps else None
        period_end = max(period_stamps) if period_stamps else None
        result.append(
            serialize_payout(
                payout,
                business_name=business.name if business else None,
                commissions=commission_rows,
                period_start=period_start,
                period_end=period_end,
            )
        )
    return result
