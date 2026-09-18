from __future__ import annotations

import secrets
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import TestFinancialOperation
from app.modules.finance.providers.base import ProviderResult
from app.modules.finance.providers.mapping import map_test_payment_status, map_test_payout_status

TEST_PROVIDER = "TEST"


class TestFinancialProvider:
    name = TEST_PROVIDER

    def __init__(self, db: AsyncSession):
        self.db = db

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
        return await self._create("payment", order_id, "PROCESSING")

    async def get_payment_status(self, provider_transaction_id: str) -> ProviderResult:
        return await self._status("payment", provider_transaction_id, map_test_payment_status)

    async def cancel_payment(self, provider_transaction_id: str) -> ProviderResult:
        return await self._set("payment", provider_transaction_id, "PAYMENT_CANCELLED", map_test_payment_status)

    async def refund_payment(self, provider_transaction_id: str, amount: Decimal | None = None) -> ProviderResult:
        return await self.cancel_payment(provider_transaction_id)

    async def create_recipient(self, *, payload: dict) -> ProviderResult:
        recipient_id = f"test_rcp_{secrets.token_hex(6)}"
        return ProviderResult(True, TEST_PROVIDER, recipient_id, "ACTIVE")

    async def verify_recipient(self, provider_recipient_id: str) -> ProviderResult:
        return ProviderResult(True, TEST_PROVIDER, provider_recipient_id, "VERIFIED")

    async def create_payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: str,
        recipient: dict,
        description: str | None = None,
    ) -> ProviderResult:
        return await self._create("payout", order_id, "PROCESSING")

    async def get_payout_status(self, provider_transaction_id: str) -> ProviderResult:
        return await self._status("payout", provider_transaction_id, map_test_payout_status)

    async def set_status(self, provider_transaction_id: str, status: str) -> ProviderResult:
        row = await self.db.scalar(
            select(TestFinancialOperation).where(
                TestFinancialOperation.provider_transaction_id == provider_transaction_id
            )
        )
        if not row:
            return ProviderResult(False, TEST_PROVIDER, provider_transaction_id, None, error_code="NOT_FOUND")
        mapper = map_test_payment_status if row.kind == "payment" else map_test_payout_status
        return await self._set(row.kind, provider_transaction_id, status, mapper)

    async def _create(self, kind: str, order_id: str, status: str) -> ProviderResult:
        existing = await self.db.scalar(
            select(TestFinancialOperation).where(
                TestFinancialOperation.reference_type == kind,
                TestFinancialOperation.reference_id == order_id,
            )
        )
        if existing:
            mapper = map_test_payment_status if kind == "payment" else map_test_payout_status
            return ProviderResult(
                True,
                TEST_PROVIDER,
                existing.provider_transaction_id,
                mapper(existing.status),
                raw_status=existing.status,
            )
        tx_id = f"test_{kind}_{secrets.token_hex(8)}"
        self.db.add(
            TestFinancialOperation(
                kind=kind,
                provider_transaction_id=tx_id,
                status=status,
                reference_type=kind,
                reference_id=order_id,
            )
        )
        await self.db.flush()
        mapper = map_test_payment_status if kind == "payment" else map_test_payout_status
        return ProviderResult(True, TEST_PROVIDER, tx_id, mapper(status), raw_status=status)

    async def _status(self, kind: str, tx_id: str, mapper) -> ProviderResult:
        row = await self.db.scalar(
            select(TestFinancialOperation).where(TestFinancialOperation.provider_transaction_id == tx_id)
        )
        if not row:
            return ProviderResult(False, TEST_PROVIDER, tx_id, None, error_code="NOT_FOUND")
        return ProviderResult(True, TEST_PROVIDER, tx_id, mapper(row.status), raw_status=row.status)

    async def _set(self, kind: str, tx_id: str, status: str, mapper) -> ProviderResult:
        row = await self.db.scalar(
            select(TestFinancialOperation).where(TestFinancialOperation.provider_transaction_id == tx_id)
        )
        if not row:
            return ProviderResult(False, TEST_PROVIDER, tx_id, None, error_code="NOT_FOUND")
        row.status = status
        await self.db.flush()
        return ProviderResult(True, TEST_PROVIDER, tx_id, mapper(status), raw_status=status)
