from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import FinancialIdempotencyKey, TermsAcceptance


async def claim_idempotency(
    db: AsyncSession,
    key: str,
    operation_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
) -> bool:
    existing = await db.scalar(select(FinancialIdempotencyKey.id).where(FinancialIdempotencyKey.key == key))
    if existing:
        return False
    try:
        async with db.begin_nested():
            db.add(
                FinancialIdempotencyKey(
                    key=key,
                    operation_type=operation_type,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id is not None else None,
                )
            )
            await db.flush()
        return True
    except IntegrityError:
        return False
