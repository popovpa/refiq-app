from __future__ import annotations

from app.common.enums import PayoutStatus

# Official T-Bank Acquiring statuses:
# https://developer.tbank.ru/eacq/api/get-state
TBANK_PAYMENT_SUCCESS = {"CONFIRMED"}
TBANK_PAYMENT_FAILED = {"REJECTED", "DEADLINE_EXPIRED", "AUTH_FAIL", "CANCELED"}
TBANK_PAYMENT_CANCELLED = {"CANCELED", "REVERSED", "REFUNDED"}
TBANK_PAYMENT_PROCESSING = {
    "NEW",
    "FORM_SHOWED",
    "PREAUTHORIZING",
    "AUTHORIZING",
    "AUTHORIZED",
    "3DS_CHECKING",
    "3DS_CHECKED",
    "CONFIRMING",
    "REFUNDING",
    "REVERSING",
}

# Official T-Bank e2c / A2C payout statuses
TBANK_PAYOUT_SUCCESS = {"COMPLETED"}
TBANK_PAYOUT_FAILED = {"REJECTED"}
TBANK_PAYOUT_PROCESSING = {
    "NEW",
    "CHECKING",
    "CHECKED",
    "COMPLETING",
    "CREDIT_CHECKING",
    "CREDIT_CHECKED",
}

INTERNAL_PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
INTERNAL_PAYMENT_FAILED = "PAYMENT_FAILED"
INTERNAL_PAYMENT_CANCELLED = "PAYMENT_CANCELLED"
INTERNAL_PAYMENT_PROCESSING = "PAYMENT_PROCESSING"

TEST_PAYMENT_STATUSES = {
    "PAYMENT_SUCCEEDED",
    "PAYMENT_FAILED",
    "PAYMENT_CANCELLED",
    "PROCESSING",
}
TEST_PAYOUT_STATUSES = {
    "PAYOUT_SUCCEEDED",
    "PAYOUT_FAILED",
    "PROCESSING",
}


def map_tbank_payment_status(status: str | None) -> str:
    value = (status or "").upper()
    if value in TBANK_PAYMENT_SUCCESS:
        return INTERNAL_PAYMENT_SUCCEEDED
    if value in TBANK_PAYMENT_CANCELLED:
        return INTERNAL_PAYMENT_CANCELLED
    if value in TBANK_PAYMENT_FAILED:
        return INTERNAL_PAYMENT_FAILED
    return INTERNAL_PAYMENT_PROCESSING


def map_tbank_payout_status(status: str | None) -> str:
    value = (status or "").upper()
    if value in TBANK_PAYOUT_SUCCESS:
        return PayoutStatus.PAID.value
    if value in TBANK_PAYOUT_FAILED:
        return PayoutStatus.FAILED.value
    return PayoutStatus.PROCESSING.value


def map_test_payment_status(status: str | None) -> str:
    value = (status or "").upper()
    if value in {"PAYMENT_SUCCEEDED", "SUCCEEDED", "CONFIRMED"}:
        return INTERNAL_PAYMENT_SUCCEEDED
    if value in {"PAYMENT_FAILED", "FAILED"}:
        return INTERNAL_PAYMENT_FAILED
    if value in {"PAYMENT_CANCELLED", "CANCELLED"}:
        return INTERNAL_PAYMENT_CANCELLED
    return INTERNAL_PAYMENT_PROCESSING


def map_test_payout_status(status: str | None) -> str:
    value = (status or "").upper()
    if value in {"PAYOUT_SUCCEEDED", "SUCCEEDED", "COMPLETED", "PAID"}:
        return PayoutStatus.PAID.value
    if value in {"PAYOUT_FAILED", "FAILED", "REJECTED"}:
        return PayoutStatus.FAILED.value
    return PayoutStatus.PROCESSING.value
