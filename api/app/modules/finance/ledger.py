from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import FinancialOperationType, FinancialScope, SupportedCurrency
from app.modules.finance.models import FinancialEntry
from app.modules.finance.money import as_money, assert_rub


async def record_entry(
    db: AsyncSession,
    *,
    scope: FinancialScope | str,
    operation_type: FinancialOperationType | str,
    amount,
    currency: str = SupportedCurrency.RUB.value,
    reference_type: str,
    reference_id: str | int,
    business_id: int | None = None,
    partner_id: int | None = None,
    legal_entity_id: int | None = None,
    metadata: dict | None = None,
) -> FinancialEntry:
    entry = FinancialEntry(
        scope=scope.value if hasattr(scope, "value") else scope,
        operation_type=operation_type.value if hasattr(operation_type, "value") else operation_type,
        amount=as_money(amount),
        currency=assert_rub(currency),
        reference_type=reference_type,
        reference_id=str(reference_id),
        business_id=business_id,
        partner_id=partner_id,
        legal_entity_id=legal_entity_id,
        metadata_=metadata,
    )
    db.add(entry)
    await db.flush()
    return entry
