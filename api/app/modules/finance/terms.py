from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.finance.models import TermsAcceptance


async def record_terms_acceptance(
    db: AsyncSession,
    *,
    user_id: int,
    context: str,
    document_type: str = "platform_terms",
    document_version: str = "2026-09-01",
    legal_entity_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TermsAcceptance:
    existing = await db.scalar(
        select(TermsAcceptance).where(
            TermsAcceptance.user_id == user_id,
            TermsAcceptance.context == context,
            TermsAcceptance.document_type == document_type,
            TermsAcceptance.document_version == document_version,
        )
    )
    if existing:
        return existing
    item = TermsAcceptance(
        user_id=user_id,
        legal_entity_id=legal_entity_id,
        context=context,
        document_type=document_type,
        document_version=document_version,
        accepted_at=datetime.now(timezone.utc),
        ip_address=(ip_address or "")[:45] or None,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(item)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(TermsAcceptance).where(
                TermsAcceptance.user_id == user_id,
                TermsAcceptance.context == context,
                TermsAcceptance.document_type == document_type,
                TermsAcceptance.document_version == document_version,
            )
        )
        if existing:
            return existing
        raise
    return item
