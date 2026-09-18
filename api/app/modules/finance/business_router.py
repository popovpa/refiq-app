from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import FinancePermission, ProfileStatus, TermsContext
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.ids import parse_id
from app.modules.billing.models import BillingTransaction, BusinessSubscription
from app.modules.businesses.models import Business
from app.modules.finance.audit import record_audit
from app.modules.finance.billing import (
    create_invoice_payment,
    ensure_billing_profile,
    ensure_default_plan,
    serialize_subscription,
    start_business_subscription,
)
from app.modules.finance.bootstrap import ensure_business_legal_entity
from app.modules.finance.commission import earnings_breakdown
from app.modules.finance.errors import fin_error
from app.modules.finance.legal import LegalEntityUpdate, serialize_legal_entity
from app.modules.finance.models import BillingInvoice, LegalEntity, Plan, PlanVersion
from app.modules.finance.verification import LegalEntityVerificationService
from app.modules.finance.money import as_money
from app.modules.finance.permissions import require_business_finance
from app.modules.finance.payouts import confirm_payout, serialize_payout
from app.modules.finance.reversal import reverse_conversion
from app.modules.finance.serialize import serialize_billing_profile
from app.modules.finance.suspension import is_partner_traffic_suspended
from app.modules.finance.terms import record_terms_acceptance
from app.modules.conversions.models import Conversion
from app.modules.partners.models import PartnerProfile
from app.modules.partners.privacy import partner_public_display_name_from, strip_partner_contact_fields
from app.modules.payouts.models import Payout
from app.modules.users.models import User

router = APIRouter()


class BillingProfileUpdate(BaseModel):
    billing_email: EmailStr | None = None


class TermsAcceptRequest(BaseModel):
    document_type: str = "platform_terms"
    document_version: str = "2026-09-01"


class ReverseConversionRequest(BaseModel):
    reason: str
    comment: str | None = Field(default=None, max_length=1000)


async def _business(session_data: dict, db: AsyncSession) -> Business:
    business = await db.scalar(select(Business).where(Business.id == parse_id(session_data["active_business_id"])))
    if not business:
        raise NotFoundError("Business")
    await ensure_business_legal_entity(db, business)
    return business


def _mode_payload() -> dict:
    return {
        "financial_mode": settings.financial_mode_label,
        "financial_transactions_enabled": settings.FINANCIAL_TRANSACTIONS_ENABLED,
        "live": settings.live_financial_transactions_allowed,
    }


@router.get("/legal-entity")
async def get_legal_entity(
    session_data: dict = Depends(require_business_finance(FinancePermission.FINANCE_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    entity = await db.get(LegalEntity, business.legal_entity_id) if business.legal_entity_id else None
    return {"legal_entity": serialize_legal_entity(entity), **_mode_payload()}


@router.patch("/legal-entity")
async def patch_legal_entity(
    data: LegalEntityUpdate,
    session_data: dict = Depends(require_business_finance(FinancePermission.LEGAL_ENTITY_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    if not business.legal_entity_id:
        raise NotFoundError("LegalEntity")
    dumped = data.model_dump(exclude_unset=True)
    submit = bool(dumped.pop("submit", False))
    entity = await LegalEntityVerificationService(db).apply_user_update(
        business.legal_entity_id,
        dumped,
        submit=submit,
        actor_user_id=parse_id(session_data["user_id"]),
    )
    business.legal_name = entity.legal_name
    business.country = entity.country
    await db.refresh(entity)
    return {"legal_entity": serialize_legal_entity(entity)}


@router.get("/billing-profile")
async def get_billing_profile(
    session_data: dict = Depends(require_business_finance(FinancePermission.FINANCE_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    profile = await ensure_billing_profile(db, business)
    return {"billing_profile": serialize_billing_profile(profile), **_mode_payload()}


@router.patch("/billing-profile")
async def patch_billing_profile(
    data: BillingProfileUpdate,
    session_data: dict = Depends(require_business_finance(FinancePermission.BILLING_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    profile = await ensure_billing_profile(db, business)
    if data.billing_email is not None:
        profile.billing_email = str(data.billing_email).lower()
        if profile.status == ProfileStatus.INCOMPLETE.value:
            profile.status = ProfileStatus.ACTIVE.value
    await record_audit(
        db,
        action="billing_profile.updated",
        entity_type="billing_profile",
        entity_id=profile.id,
        actor_user_id=parse_id(session_data["user_id"]),
        new_status=profile.status,
    )
    await db.refresh(profile)
    return {"billing_profile": serialize_billing_profile(profile)}


@router.get("/subscription")
async def get_subscription(
    session_data: dict = Depends(require_business_finance(FinancePermission.FINANCE_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    sub = await start_business_subscription(db, business)
    plan, version = await ensure_default_plan(db)
    if sub.plan_id:
        plan = await db.get(Plan, sub.plan_id) or plan
    if sub.plan_version_id:
        version = await db.get(PlanVersion, sub.plan_version_id) or version
    return {"subscription": serialize_subscription(sub, plan, version), **_mode_payload()}


@router.get("/billing-history")
async def billing_history(
    session_data: dict = Depends(require_business_finance(FinancePermission.FINANCE_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    invoices = (
        await db.execute(
            select(BillingInvoice)
            .where(BillingInvoice.business_id == business.id)
            .order_by(BillingInvoice.created_at.desc())
        )
    ).scalars().all()
    txs = (
        await db.execute(
            select(BillingTransaction)
            .where(BillingTransaction.business_id == business.id)
            .order_by(BillingTransaction.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return {
        "invoices": [
            {
                "id": item.id,
                "amount": float(as_money(item.amount)),
                "currency": item.currency,
                "status": item.status,
                "period_start": item.period_start.isoformat(),
                "period_end": item.period_end.isoformat(),
                "due_at": item.due_at.isoformat(),
                "paid_at": item.paid_at.isoformat() if item.paid_at else None,
            }
            for item in invoices
        ],
        "transactions": [
            {
                "id": tx.id,
                "type": tx.type,
                "amount": float(as_money(tx.amount)),
                "currency": tx.currency,
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in txs
        ],
        **_mode_payload(),
    }


@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    session_data: dict = Depends(require_business_finance(FinancePermission.BILLING_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    invoice = await db.scalar(
        select(BillingInvoice).where(
            BillingInvoice.id == parse_id(invoice_id),
            BillingInvoice.business_id == business.id,
        )
    )
    if not invoice:
        raise NotFoundError("Invoice")
    tx = await create_invoice_payment(db, invoice, actor_user_id=parse_id(session_data["user_id"]))
    return {
        "transaction_id": tx.id,
        "status": tx.status,
        "payment_url": (tx.metadata_ or {}).get("payment_url") if tx.metadata_ else None,
        **_mode_payload(),
    }


@router.get("/partner-obligations")
async def partner_obligations(
    session_data: dict = Depends(require_business_finance(FinancePermission.PAYOUT_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    totals = await earnings_breakdown(db, business_id=business.id)
    return {
        "accrued": totals["hold"] + totals["pending"] + totals["available"] + totals["payout_pending"] + totals["paid"],
        "pending_confirmation": totals["payout_pending"],
        "payable": totals["available"],
        "overdue": 0,
        "paid": totals["paid"],
        "breakdown": totals,
        "partner_traffic_suspended": await is_partner_traffic_suspended(db, business.id),
        **_mode_payload(),
    }


@router.get("/payouts")
async def list_payouts(
    status: str | None = Query(default=None),
    session_data: dict = Depends(require_business_finance(FinancePermission.PAYOUT_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    all_rows = (
        await db.execute(
            select(Payout).where(Payout.payer_business_id == business.id).order_by(Payout.created_at.desc())
        )
    ).scalars().all()
    rows = [row for row in all_rows if not status or row.status == status]
    partner_ids = [row.partner_id for row in rows]
    names: dict[int, str] = {}
    if partner_ids:
        partner_rows = (
            await db.execute(
                select(PartnerProfile, User)
                .join(User, PartnerProfile.user_id == User.id)
                .where(PartnerProfile.id.in_(partner_ids))
            )
        ).all()
        for profile, user in partner_rows:
            names[profile.id] = partner_public_display_name_from(profile, user)
    overdue_amount = sum(float(as_money(p.amount)) for p in all_rows if p.status == "overdue")
    pending_confirmation = sum(
        float(as_money(p.amount))
        for p in all_rows
        if p.status in {"created", "awaiting_confirmation", "pending"}
    )
    processing_amount = sum(float(as_money(p.amount)) for p in all_rows if p.status == "processing")
    totals = await earnings_breakdown(db, business_id=business.id)
    items = [
        strip_partner_contact_fields(serialize_payout(p, partner_name=names.get(p.partner_id)))
        for p in rows
    ]
    return {
        "items": items,
        "total": len(items),
        "payable_amount": totals["available"],
        "pending_confirmation": pending_confirmation,
        "processing_amount": processing_amount,
        "overdue_amount": overdue_amount,
        "paid_amount": totals["paid"],
        "partner_traffic_suspended": await is_partner_traffic_suspended(db, business.id),
        **_mode_payload(),
    }


@router.post("/payouts/{payout_id}/confirm")
async def confirm_business_payout(
    payout_id: str,
    session_data: dict = Depends(require_business_finance(FinancePermission.PAYOUT_CONFIRM)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    payout = await db.scalar(
        select(Payout).where(Payout.id == parse_id(payout_id), Payout.payer_business_id == business.id)
    )
    if not payout:
        raise NotFoundError("Payout")
    payout = await confirm_payout(db, payout, actor_user_id=parse_id(session_data["user_id"]))
    return {"payout": serialize_payout(payout), **_mode_payload()}


@router.post("/conversions/{conversion_id}/reverse")
async def reverse_business_conversion(
    conversion_id: str,
    data: ReverseConversionRequest,
    session_data: dict = Depends(require_business_finance(FinancePermission.PAYOUT_CONFIRM)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    conversion = await db.scalar(
        select(Conversion).where(
            Conversion.id == parse_id(conversion_id),
            Conversion.business_id == business.id,
        )
    )
    if not conversion:
        raise NotFoundError("Conversion")
    result = await reverse_conversion(
        db,
        conversion,
        reason=data.reason,
        comment=data.comment,
        actor_user_id=parse_id(session_data["user_id"]),
    )
    return {**result, **_mode_payload()}


@router.post("/terms/accept")
async def accept_business_terms(
    data: TermsAcceptRequest,
    request: Request,
    session_data: dict = Depends(require_business_finance(FinancePermission.LEGAL_ENTITY_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    business = await _business(session_data, db)
    item = await record_terms_acceptance(
        db,
        user_id=parse_id(session_data["user_id"]),
        context=TermsContext.BUSINESS.value,
        document_type=data.document_type,
        document_version=data.document_version,
        legal_entity_id=business.legal_entity_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"accepted_at": item.accepted_at.isoformat(), "document_version": item.document_version}
