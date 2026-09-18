from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.finance.providers.test_provider import TestFinancialProvider
from app.modules.finance.providers.tbank import FailClosedProvider, TBankPaymentProvider, TBankPayoutProvider

logger = structlog.get_logger()

_payment_override = None
_payout_override = None
_tbank_payment_ctor = TBankPaymentProvider
_tbank_payout_ctor = TBankPayoutProvider


def set_payment_provider_override(provider) -> None:
    global _payment_override
    _payment_override = provider


def set_payout_provider_override(provider) -> None:
    global _payout_override
    _payout_override = provider


def set_tbank_constructors(payment_ctor=None, payout_ctor=None) -> None:
    global _tbank_payment_ctor, _tbank_payout_ctor
    if payment_ctor is not None:
        _tbank_payment_ctor = payment_ctor
    if payout_ctor is not None:
        _tbank_payout_ctor = payout_ctor


def reset_provider_overrides() -> None:
    global _payment_override, _payout_override, _tbank_payment_ctor, _tbank_payout_ctor
    _payment_override = None
    _payout_override = None
    _tbank_payment_ctor = TBankPaymentProvider
    _tbank_payout_ctor = TBankPayoutProvider


def get_payment_provider(db: AsyncSession):
    if _payment_override is not None:
        return _payment_override
    if settings.live_financial_transactions_allowed:
        return _tbank_payment_ctor()
    if settings.FINANCIAL_TRANSACTIONS_ENABLED:
        return FailClosedProvider()
    return TestFinancialProvider(db)


def get_payout_provider(db: AsyncSession):
    if _payout_override is not None:
        return _payout_override
    if settings.live_financial_transactions_allowed:
        return _tbank_payout_ctor()
    if settings.FINANCIAL_TRANSACTIONS_ENABLED:
        return FailClosedProvider()
    return TestFinancialProvider(db)


def log_financial_mode() -> None:
    logger.info("FINANCIAL MODE: %s" % settings.financial_mode_label)


def validate_live_startup() -> None:
    log_financial_mode()
    if settings.FINANCIAL_TRANSACTIONS_ENABLED and settings.is_production:
        if not settings.live_financial_transactions_allowed:
            raise RuntimeError(
                "Production live financial mode requires FINANCIAL_TRANSACTIONS_ENABLED=true, "
                "provider=TBANK, and configured T-Bank credentials"
            )
