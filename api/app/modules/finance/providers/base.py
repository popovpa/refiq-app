from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    provider: str
    provider_transaction_id: str | None
    provider_status: str | None
    payment_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_status: str | None = None


class PaymentProvider(Protocol):
    name: str

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
    ) -> ProviderResult: ...

    async def get_payment_status(self, provider_transaction_id: str) -> ProviderResult: ...

    async def cancel_payment(self, provider_transaction_id: str) -> ProviderResult: ...

    async def refund_payment(self, provider_transaction_id: str, amount: Decimal | None = None) -> ProviderResult: ...


class PayoutProvider(Protocol):
    name: str

    async def create_recipient(self, *, payload: dict) -> ProviderResult: ...

    async def verify_recipient(self, provider_recipient_id: str) -> ProviderResult: ...

    async def create_payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: str,
        recipient: dict,
        description: str | None = None,
    ) -> ProviderResult: ...

    async def get_payout_status(self, provider_transaction_id: str) -> ProviderResult: ...
