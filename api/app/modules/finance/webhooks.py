from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError
from fastapi import Depends

from app.modules.billing.models import BillingTransaction
from app.modules.finance.audit import record_audit
from app.modules.finance.billing import apply_payment_status
from app.modules.finance.errors import fin_error
from app.modules.finance.models import ProviderWebhookEvent
from app.modules.finance.payouts import mark_payout_failed, mark_payout_paid
from app.modules.finance.providers.mapping import map_tbank_payment_status, map_tbank_payout_status
from app.modules.finance.providers.tbank import verify_tbank_notification
from app.common.enums import PayoutFailureClass, PayoutStatus
from app.modules.payouts.models import Payout

router = APIRouter()


def _event_id(payload: dict) -> str:
    payment_id = str(payload.get("PaymentId") or payload.get("payment_id") or "")
    status = str(payload.get("Status") or "")
    if payment_id:
        return f"{payment_id}:{status}"
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return digest


@router.post("/webhooks/tbank")
async def tbank_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_refiq_test: str | None = Header(default=None),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise fin_error("FIN_PROVIDER_ERROR", "Invalid webhook payload", 400)
    live = settings.live_financial_transactions_allowed
    password = settings.TBANK_PASSWORD or settings.TBANK_E2C_PASSWORD
    if live:
        if not password or not verify_tbank_notification(payload, password):
            raise fin_error("FIN_PROVIDER_ERROR", "Invalid T-Bank webhook signature", 401)
    elif settings.is_production:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live webhooks are disabled", 403)

    event_id = _event_id(payload)
    existing = await db.scalar(
        select(ProviderWebhookEvent.id).where(
            ProviderWebhookEvent.provider == "TBANK",
            ProviderWebhookEvent.external_event_id == event_id,
        )
    )
    if existing:
        return {"status": "duplicate"}
    db.add(
        ProviderWebhookEvent(
            provider="TBANK",
            external_event_id=event_id,
            event_type=payload.get("Status"),
            provider_status=payload.get("Status"),
            payload_digest=hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest(),
        )
    )
    await db.flush()
    payment_id = str(payload.get("PaymentId") or "")
    raw_status = payload.get("Status")
    tx = await db.scalar(
        select(BillingTransaction).where(BillingTransaction.provider_transaction_id == payment_id)
    )
    if tx:
        await apply_payment_status(db, tx, map_tbank_payment_status(raw_status), raw_status)
        await record_audit(
            db,
            action="provider.webhook",
            entity_type="billing_transaction",
            entity_id=tx.id,
            system_actor="tbank",
            new_status=tx.status,
            metadata={"payment_id": payment_id},
        )
        return {"status": "ok", "kind": "payment"}
    payout = await db.scalar(select(Payout).where(Payout.provider_transaction_id == payment_id))
    if payout:
        mapped = map_tbank_payout_status(raw_status)
        payout.provider_status = raw_status
        if mapped == PayoutStatus.PAID.value:
            await mark_payout_paid(db, payout)
        elif mapped == PayoutStatus.FAILED.value:
            await mark_payout_failed(
                db,
                payout,
                failure_class=PayoutFailureClass.PROVIDER_ERROR.value,
                message=str(payload.get("Message") or "") or None,
            )
        await record_audit(
            db,
            action="provider.webhook",
            entity_type="payout",
            entity_id=payout.id,
            system_actor="tbank",
            new_status=payout.status,
            metadata={"payment_id": payment_id},
        )
        return {"status": "ok", "kind": "payout"}
    return {"status": "ignored"}
