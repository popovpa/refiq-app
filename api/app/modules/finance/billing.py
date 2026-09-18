from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    FinancialOperationType,
    FinancialScope,
    InvoiceStatus,
    ProfileStatus,
    SubscriptionStatus,
)
from app.core.config import settings
from app.modules.billing.models import BillingTransaction, BusinessSubscription, PlatformFee
from app.modules.businesses.models import Business
from app.modules.finance.audit import record_audit
from app.modules.finance.errors import fin_error
from app.modules.finance.idempotency import claim_idempotency
from app.modules.finance.ledger import record_entry
from app.modules.finance.legal import require_verified_legal_entity
from app.modules.finance.metrics import inc
from app.modules.finance.models import BillingInvoice, BusinessBillingProfile, LegalEntity, Plan, PlanVersion
from app.modules.finance.money import as_money, assert_rub
from app.modules.finance.providers.factory import get_payment_provider
from app.modules.finance.providers.mapping import INTERNAL_PAYMENT_FAILED, INTERNAL_PAYMENT_SUCCEEDED

PRO_PLAN_CODE = "pro"


async def ensure_default_plan(db: AsyncSession) -> tuple[Plan, PlanVersion]:
    plan = await db.scalar(select(Plan).where(Plan.code == PRO_PLAN_CODE))
    if plan is None:
        plan = Plan(code=PRO_PLAN_CODE, name="Pro", billing_period="MONTHLY", is_active=True)
        db.add(plan)
        await db.flush()
        version = PlanVersion(
            plan_id=plan.id,
            version=1,
            amount=as_money(settings.PLAN_PRO_AMOUNT),
            currency="RUB",
            effective_from=datetime.now(timezone.utc),
        )
        db.add(version)
        await db.flush()
        return plan, version
    version = (
        await db.execute(
            select(PlanVersion).where(PlanVersion.plan_id == plan.id).order_by(PlanVersion.version.desc())
        )
    ).scalars().first()
    if version is None:
        version = PlanVersion(
            plan_id=plan.id,
            version=1,
            amount=as_money(settings.PLAN_PRO_AMOUNT),
            currency="RUB",
            effective_from=datetime.now(timezone.utc),
        )
        db.add(version)
        await db.flush()
    return plan, version


async def start_business_subscription(db: AsyncSession, business: Business) -> BusinessSubscription:
    existing = await db.scalar(
        select(BusinessSubscription)
        .where(BusinessSubscription.business_id == business.id)
        .order_by(BusinessSubscription.id.desc())
    )
    if existing:
        return existing
    plan, version = await ensure_default_plan(db)
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=settings.SUBSCRIPTION_TRIAL_DAYS)
    sub = BusinessSubscription(
        business_id=business.id,
        plan=plan.code,
        plan_id=plan.id,
        plan_version_id=version.id,
        status=SubscriptionStatus.TRIAL.value,
        started_at=now,
        trial_ends_at=trial_end,
        current_period_start=now,
        current_period_end=trial_end,
        expires_at=trial_end,
    )
    db.add(sub)
    await db.flush()
    await record_audit(
        db,
        action="subscription.started",
        entity_type="subscription",
        entity_id=sub.id,
        system_actor="system",
        new_status=sub.status,
    )
    return sub


async def ensure_billing_profile(db: AsyncSession, business: Business) -> BusinessBillingProfile:
    profile = await db.scalar(
        select(BusinessBillingProfile).where(BusinessBillingProfile.business_id == business.id)
    )
    if profile:
        if business.legal_entity_id and profile.legal_entity_id != business.legal_entity_id:
            profile.legal_entity_id = business.legal_entity_id
        return profile
    profile = BusinessBillingProfile(
        business_id=business.id,
        legal_entity_id=business.legal_entity_id,
        provider="TBANK",
        status=ProfileStatus.INCOMPLETE.value,
    )
    db.add(profile)
    await db.flush()
    return profile


def _period_end(start: datetime) -> datetime:
    month = start.month + 1
    year = start.year + (1 if month > 12 else 0)
    month = 1 if month > 12 else month
    try:
        return start.replace(year=year, month=month)
    except ValueError:
        return start.replace(year=year, month=month, day=28)


async def generate_subscription_invoices(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    created = 0
    subs = (
        await db.execute(
            select(BusinessSubscription).where(
                BusinessSubscription.status.in_(
                    [
                        SubscriptionStatus.TRIAL.value,
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.PAST_DUE.value,
                    ]
                )
            )
        )
    ).scalars().all()
    for sub in subs:
        due_anchor = sub.trial_ends_at if sub.status == SubscriptionStatus.TRIAL.value else sub.current_period_end
        if due_anchor and due_anchor > now:
            continue
        plan, version = await _plan_for_sub(db, sub)
        period_start = due_anchor or now
        period_end = _period_end(period_start)
        key = f"invoice:{sub.business_id}:{period_start.date().isoformat()}"
        if not await claim_idempotency(db, key, "subscription_invoice", resource_type="subscription", resource_id=sub.id):
            continue
        invoice = BillingInvoice(
            business_id=sub.business_id,
            subscription_id=sub.id,
            plan_id=plan.id if plan else None,
            plan_version_id=version.id if version else sub.plan_version_id,
            period_start=period_start,
            period_end=period_end,
            amount=as_money(version.amount) if version else as_money(settings.PLAN_PRO_AMOUNT),
            currency="RUB",
            status=InvoiceStatus.OPEN.value,
            due_at=period_start,
            idempotency_key=key,
        )
        db.add(invoice)
        await db.flush()
        db.add(
            PlatformFee(
                business_id=sub.business_id,
                invoice_id=invoice.id,
                fee_type="subscription",
                amount=invoice.amount,
                currency="RUB",
                period_start=period_start,
                period_end=period_end,
                status="pending",
            )
        )
        inc("billing_transaction_created_total")
        await record_entry(
            db,
            scope=FinancialScope.BUSINESS_BILLING,
            operation_type=FinancialOperationType.SUBSCRIPTION_CHARGE_CREATED,
            amount=invoice.amount,
            currency="RUB",
            reference_type="invoice",
            reference_id=invoice.id,
            business_id=sub.business_id,
        )
        if sub.status == SubscriptionStatus.TRIAL.value:
            sub.status = SubscriptionStatus.PAST_DUE.value
            sub.grace_ends_at = now + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
        elif sub.status == SubscriptionStatus.ACTIVE.value:
            sub.status = SubscriptionStatus.PAST_DUE.value
            sub.grace_ends_at = now + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
        sub.current_period_start = period_start
        sub.current_period_end = period_end
        created += 1
    return created


async def process_past_due(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    count = 0
    subs = (
        await db.execute(
            select(BusinessSubscription).where(BusinessSubscription.status == SubscriptionStatus.PAST_DUE.value)
        )
    ).scalars().all()
    for sub in subs:
        if sub.grace_ends_at and sub.grace_ends_at <= now:
            old = sub.status
            sub.status = SubscriptionStatus.SUSPENDED.value
            count += 1
            await record_audit(
                db,
                action="subscription.suspended",
                entity_type="subscription",
                entity_id=sub.id,
                system_actor="scheduler",
                old_status=old,
                new_status=sub.status,
            )
    invoices = (
        await db.execute(
            select(BillingInvoice).where(
                BillingInvoice.status == InvoiceStatus.OPEN.value,
                BillingInvoice.due_at < now,
            )
        )
    ).scalars().all()
    for invoice in invoices:
        invoice.status = InvoiceStatus.PAST_DUE.value
    return count


async def create_invoice_payment(
    db: AsyncSession,
    invoice: BillingInvoice,
    *,
    actor_user_id: int | None = None,
    success_url: str | None = None,
    fail_url: str | None = None,
) -> BillingTransaction:
    assert_rub(invoice.currency)
    business = await db.scalar(select(Business).where(Business.id == invoice.business_id))
    if not business:
        raise fin_error("FIN_BUSINESS_NOT_FOUND", "Business not found", 404)
    entity = await db.get(LegalEntity, business.legal_entity_id) if business.legal_entity_id else None
    require_verified_legal_entity(entity)
    profile = await ensure_billing_profile(db, business)
    if invoice.status in {InvoiceStatus.PAID.value, InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value}:
        raise fin_error("FIN_PAYOUT_ALREADY_PROCESSED", "Invoice is not payable")
    key = f"payment:invoice:{invoice.id}"
    existing = await db.scalar(
        select(BillingTransaction).where(BillingTransaction.idempotency_key == key)
    )
    if existing and existing.status not in {"failed", "cancelled"}:
        return existing
    if not await claim_idempotency(db, key, "invoice_payment", resource_type="invoice", resource_id=invoice.id):
        existing = await db.scalar(select(BillingTransaction).where(BillingTransaction.idempotency_key == key))
        if existing:
            return existing
    tx = BillingTransaction(
        business_id=invoice.business_id,
        invoice_id=invoice.id,
        type="subscription_payment",
        amount=as_money(invoice.amount),
        currency="RUB",
        status="created",
        provider=profile.provider or "TBANK",
        idempotency_key=key,
        reference_type="invoice",
        reference_id=str(invoice.id),
    )
    db.add(tx)
    await db.flush()
    await record_entry(
        db,
        scope=FinancialScope.BUSINESS_BILLING,
        operation_type=FinancialOperationType.PAYMENT_CREATED,
        amount=tx.amount,
        currency="RUB",
        reference_type="billing_transaction",
        reference_id=tx.id,
        business_id=invoice.business_id,
        legal_entity_id=business.legal_entity_id,
    )
    provider = get_payment_provider(db)
    result = await provider.create_payment(
        amount=as_money(invoice.amount),
        currency="RUB",
        order_id=f"inv-{invoice.id}",
        description=f"RefIQ subscription invoice {invoice.id}",
        customer_key=profile.provider_customer_id or f"biz-{business.id}",
        success_url=success_url,
        fail_url=fail_url,
    )
    tx.provider = result.provider
    tx.provider_transaction_id = result.provider_transaction_id
    tx.provider_status = result.raw_status or result.provider_status
    if result.ok:
        tx.status = "processing"
        tx.metadata_ = {"payment_url": result.payment_url} if result.payment_url else None
        await record_entry(
            db,
            scope=FinancialScope.BUSINESS_BILLING,
            operation_type=FinancialOperationType.PAYMENT_PROCESSING,
            amount=tx.amount,
            currency="RUB",
            reference_type="billing_transaction",
            reference_id=tx.id,
            business_id=invoice.business_id,
        )
    else:
        tx.status = "failed"
        inc("billing_payment_failed_total")
        inc("financial_provider_error_total")
        await record_entry(
            db,
            scope=FinancialScope.BUSINESS_BILLING,
            operation_type=FinancialOperationType.PAYMENT_FAILED,
            amount=tx.amount,
            currency="RUB",
            reference_type="billing_transaction",
            reference_id=tx.id,
            business_id=invoice.business_id,
        )
    await record_audit(
        db,
        action="billing.payment_created",
        entity_type="billing_transaction",
        entity_id=tx.id,
        actor_user_id=actor_user_id,
        system_actor=None if actor_user_id else "system",
        new_status=tx.status,
        metadata={"live": settings.live_financial_transactions_allowed},
    )
    return tx


async def apply_payment_status(db: AsyncSession, tx: BillingTransaction, provider_status: str, raw_status: str | None = None) -> None:
    if tx.status in {"succeeded", "paid", "cancelled"}:
        return
    old = tx.status
    tx.provider_status = raw_status or provider_status
    if provider_status == INTERNAL_PAYMENT_SUCCEEDED:
        tx.status = "succeeded"
        invoice = await db.scalar(select(BillingInvoice).where(BillingInvoice.id == tx.invoice_id)) if tx.invoice_id else None
        if invoice and invoice.status != InvoiceStatus.PAID.value:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_at = datetime.now(timezone.utc)
        sub = None
        if invoice and invoice.subscription_id:
            sub = await db.scalar(select(BusinessSubscription).where(BusinessSubscription.id == invoice.subscription_id))
        if sub and sub.status in {
            SubscriptionStatus.TRIAL.value,
            SubscriptionStatus.PAST_DUE.value,
            SubscriptionStatus.SUSPENDED.value,
            SubscriptionStatus.ACTIVE.value,
        }:
            sub.status = SubscriptionStatus.ACTIVE.value
            sub.grace_ends_at = None
        await record_entry(
            db,
            scope=FinancialScope.BUSINESS_BILLING,
            operation_type=FinancialOperationType.PAYMENT_SUCCEEDED,
            amount=tx.amount,
            currency="RUB",
            reference_type="billing_transaction",
            reference_id=tx.id,
            business_id=tx.business_id,
        )
    elif provider_status == INTERNAL_PAYMENT_FAILED:
        tx.status = "failed"
        inc("billing_payment_failed_total")
        await record_entry(
            db,
            scope=FinancialScope.BUSINESS_BILLING,
            operation_type=FinancialOperationType.PAYMENT_FAILED,
            amount=tx.amount,
            currency="RUB",
            reference_type="billing_transaction",
            reference_id=tx.id,
            business_id=tx.business_id,
        )
    else:
        tx.status = "processing"
    await record_audit(
        db,
        action="billing.payment_status",
        entity_type="billing_transaction",
        entity_id=tx.id,
        system_actor="provider",
        old_status=old,
        new_status=tx.status,
    )


async def _plan_for_sub(db: AsyncSession, sub: BusinessSubscription) -> tuple[Plan | None, PlanVersion | None]:
    plan = await db.scalar(select(Plan).where(Plan.id == sub.plan_id)) if sub.plan_id else None
    version = (
        await db.scalar(select(PlanVersion).where(PlanVersion.id == sub.plan_version_id))
        if sub.plan_version_id
        else None
    )
    if plan and version:
        return plan, version
    return await ensure_default_plan(db)


def serialize_subscription(sub: BusinessSubscription | None, plan: Plan | None = None, version: PlanVersion | None = None) -> dict | None:
    if sub is None:
        return None
    return {
        "id": sub.id,
        "plan": sub.plan,
        "plan_code": plan.code if plan else sub.plan,
        "plan_name": plan.name if plan else sub.plan,
        "status": sub.status,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "grace_ends_at": sub.grace_ends_at.isoformat() if sub.grace_ends_at else None,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "next_billing_date": (sub.trial_ends_at or sub.current_period_end).isoformat()
        if (sub.trial_ends_at or sub.current_period_end)
        else None,
        "amount": float(as_money(version.amount)) if version else float(as_money(settings.PLAN_PRO_AMOUNT)),
        "currency": "RUB",
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }
