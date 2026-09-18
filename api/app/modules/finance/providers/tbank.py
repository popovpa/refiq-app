from __future__ import annotations

import hashlib
from decimal import Decimal

import httpx
import structlog

from app.core.config import settings
from app.modules.finance.errors import fin_error
from app.modules.finance.money import to_kopecks
from app.modules.finance.providers.base import ProviderResult
from app.modules.finance.providers.mapping import map_tbank_payment_status, map_tbank_payout_status

logger = structlog.get_logger()

# Official T-Bank Internet Acquiring API v2:
# https://developer.tbank.ru/eacq/api/init
# https://developer.tbank.ru/eacq/api/get-state
# Official T-Bank e2c / A2C payout API:
# POST https://securepay.tinkoff.ru/e2c/v2/Init
# POST https://securepay.tinkoff.ru/e2c/v2/Payment
# POST https://securepay.tinkoff.ru/e2c/v2/GetState


def tbank_token(payload: dict, password: str) -> str:
    values = {key: value for key, value in payload.items() if key != "Token" and not isinstance(value, (dict, list))}
    values["Password"] = password
    concatenated = "".join(str(values[key]) for key in sorted(values.keys()))
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def verify_tbank_notification(payload: dict, password: str) -> bool:
    token = str(payload.get("Token") or "")
    if not token:
        return False
    expected = tbank_token(payload, password)
    return token.lower() == expected.lower()


class _TBankClient:
    def __init__(self, *, base_url: str, terminal_key: str, password: str, timeout: float = 20):
        self.base_url = base_url.rstrip("/")
        self.terminal_key = terminal_key
        self.password = password
        self.timeout = timeout

    async def post(self, method: str, payload: dict) -> dict:
        body = {"TerminalKey": self.terminal_key, **payload}
        body["Token"] = tbank_token(body, self.password)
        url = f"{self.base_url}/{method.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("tbank_http_error", method=method)
            raise fin_error("FIN_PROVIDER_ERROR", "T-Bank request failed", 502) from exc
        if not data.get("Success", True) and data.get("ErrorCode") not in (None, "0", 0):
            logger.error("tbank_api_error", method=method, error_code=data.get("ErrorCode"))
            return data
        return data


class TBankPaymentProvider:
    name = "TBANK"

    def __init__(self):
        if not settings.tbank_payment_credentials_configured:
            raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "T-Bank payment credentials are not configured", 503)
        self.client = _TBankClient(
            base_url=settings.TBANK_ACQUIRING_BASE_URL,
            terminal_key=settings.TBANK_TERMINAL_KEY,
            password=settings.TBANK_PASSWORD,
        )

    async def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: str,
        description: str,
        notification_url: str | None = None,
        success_url: str | None = None,
        fail_url: str | None = None,
        customer_key: str | None = None,
    ) -> ProviderResult:
        payload: dict = {
            "Amount": to_kopecks(amount),
            "OrderId": order_id,
            "Description": description[:250],
        }
        if notification_url or settings.TBANK_NOTIFICATION_URL:
            payload["NotificationURL"] = notification_url or settings.TBANK_NOTIFICATION_URL
        if success_url:
            payload["SuccessURL"] = success_url
        if fail_url:
            payload["FailURL"] = fail_url
        if customer_key:
            payload["CustomerKey"] = customer_key
        data = await self.client.post("Init", payload)
        payment_id = str(data.get("PaymentId") or "") or None
        status = data.get("Status")
        ok = bool(data.get("Success", True)) and bool(payment_id)
        return ProviderResult(
            ok=ok,
            provider=self.name,
            provider_transaction_id=payment_id,
            provider_status=map_tbank_payment_status(status),
            payment_url=data.get("PaymentURL"),
            error_code=None if ok else str(data.get("ErrorCode") or "FIN_PROVIDER_ERROR"),
            error_message=None if ok else (data.get("Message") or data.get("Details")),
            raw_status=status,
        )

    async def get_payment_status(self, provider_transaction_id: str) -> ProviderResult:
        data = await self.client.post("GetState", {"PaymentId": provider_transaction_id})
        status = data.get("Status")
        ok = bool(data.get("Success", True))
        return ProviderResult(
            ok=ok,
            provider=self.name,
            provider_transaction_id=str(data.get("PaymentId") or provider_transaction_id),
            provider_status=map_tbank_payment_status(status),
            error_code=None if ok else str(data.get("ErrorCode") or "FIN_PROVIDER_ERROR"),
            error_message=None if ok else (data.get("Message") or data.get("Details")),
            raw_status=status,
        )

    async def cancel_payment(self, provider_transaction_id: str) -> ProviderResult:
        data = await self.client.post("Cancel", {"PaymentId": provider_transaction_id})
        status = data.get("Status")
        ok = bool(data.get("Success", True))
        return ProviderResult(
            ok=ok,
            provider=self.name,
            provider_transaction_id=provider_transaction_id,
            provider_status=map_tbank_payment_status(status),
            raw_status=status,
        )

    async def refund_payment(self, provider_transaction_id: str, amount: Decimal | None = None) -> ProviderResult:
        payload: dict = {"PaymentId": provider_transaction_id}
        if amount is not None:
            payload["Amount"] = to_kopecks(amount)
        data = await self.client.post("Cancel", payload)
        status = data.get("Status")
        return ProviderResult(
            ok=bool(data.get("Success", True)),
            provider=self.name,
            provider_transaction_id=provider_transaction_id,
            provider_status=map_tbank_payment_status(status),
            raw_status=status,
        )


class TBankPayoutProvider:
    name = "TBANK"

    def __init__(self):
        if not settings.tbank_payout_credentials_configured:
            raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "T-Bank payout credentials are not configured", 503)
        self.client = _TBankClient(
            base_url=settings.TBANK_E2C_BASE_URL,
            terminal_key=settings.TBANK_E2C_TERMINAL_KEY or settings.TBANK_TERMINAL_KEY,
            password=settings.TBANK_E2C_PASSWORD or settings.TBANK_PASSWORD,
        )

    async def create_recipient(self, *, payload: dict) -> ProviderResult:
        return ProviderResult(
            True,
            self.name,
            payload.get("provider_recipient_id") or payload.get("CardId"),
            "PENDING_VERIFICATION",
        )

    async def verify_recipient(self, provider_recipient_id: str) -> ProviderResult:
        return ProviderResult(True, self.name, provider_recipient_id, "VERIFIED")

    async def create_payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: str,
        recipient: dict,
        description: str | None = None,
    ) -> ProviderResult:
        payload: dict = {
            "Amount": to_kopecks(amount),
            "OrderId": order_id,
        }
        if description:
            payload["Description"] = description[:250]
        if recipient.get("CardId"):
            payload["CardId"] = recipient["CardId"]
        if recipient.get("Phone"):
            payload["Phone"] = recipient["Phone"]
        data = await self.client.post("Init", payload)
        payment_id = str(data.get("PaymentId") or "") or None
        if payment_id and not recipient.get("skip_payment_method"):
            pay = await self.client.post("Payment", {"PaymentId": payment_id})
            status = pay.get("Status") or data.get("Status")
            ok = bool(pay.get("Success", True))
            return ProviderResult(
                ok=ok,
                provider=self.name,
                provider_transaction_id=payment_id,
                provider_status=map_tbank_payout_status(status),
                error_code=None if ok else str(pay.get("ErrorCode") or "FIN_PROVIDER_ERROR"),
                error_message=None if ok else (pay.get("Message") or pay.get("Details")),
                raw_status=status,
            )
        status = data.get("Status")
        ok = bool(data.get("Success", True)) and bool(payment_id)
        return ProviderResult(
            ok=ok,
            provider=self.name,
            provider_transaction_id=payment_id,
            provider_status=map_tbank_payout_status(status),
            error_code=None if ok else str(data.get("ErrorCode") or "FIN_PROVIDER_ERROR"),
            error_message=None if ok else (data.get("Message") or data.get("Details")),
            raw_status=status,
        )

    async def get_payout_status(self, provider_transaction_id: str) -> ProviderResult:
        data = await self.client.post("GetState", {"PaymentId": provider_transaction_id})
        status = data.get("Status")
        ok = bool(data.get("Success", True))
        return ProviderResult(
            ok=ok,
            provider=self.name,
            provider_transaction_id=provider_transaction_id,
            provider_status=map_tbank_payout_status(status),
            error_code=None if ok else str(data.get("ErrorCode") or "FIN_PROVIDER_ERROR"),
            raw_status=status,
        )


class FailClosedProvider:
    name = "DISABLED"

    async def create_payment(self, **kwargs) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payments are not allowed", 503)

    async def get_payment_status(self, provider_transaction_id: str) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payments are not allowed", 503)

    async def cancel_payment(self, provider_transaction_id: str) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payments are not allowed", 503)

    async def refund_payment(self, provider_transaction_id: str, amount: Decimal | None = None) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payments are not allowed", 503)

    async def create_recipient(self, *, payload: dict) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payouts are not allowed", 503)

    async def verify_recipient(self, provider_recipient_id: str) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payouts are not allowed", 503)

    async def create_payout(self, **kwargs) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payouts are not allowed", 503)

    async def get_payout_status(self, provider_transaction_id: str) -> ProviderResult:
        raise fin_error("FIN_LIVE_TRANSACTIONS_DISABLED", "Live T-Bank payouts are not allowed", 503)
