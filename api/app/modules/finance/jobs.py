from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.modules.finance.billing import generate_subscription_invoices, process_past_due
from app.modules.finance.commission import release_due_holds
from app.modules.finance.models import FinancialJobLock
from app.modules.finance.notifications import send_payout_notifications
from app.modules.finance.payouts import generate_due_payouts, mark_overdue_payouts
from app.modules.finance.reconciliation import reconcile_open_transactions
import structlog

logger = structlog.get_logger()


def _insert_stmt(job_name: str, run_key: str, dialect: str):
    values = {"job_name": job_name, "run_key": run_key}
    if dialect == "sqlite":
        return sqlite_insert(FinancialJobLock).values(**values).on_conflict_do_nothing(
            index_elements=["job_name", "run_key"]
        )
    return pg_insert(FinancialJobLock).values(**values).on_conflict_do_nothing(
        constraint="uq_financial_job_lock"
    )


async def _claim_lock(db: AsyncSession, job_name: str, run_key: str) -> bool:
    dialect = db.bind.dialect.name if db.bind is not None else "postgresql"
    stmt = _insert_stmt(job_name, run_key, dialect).returning(FinancialJobLock.id)
    try:
        return (await db.execute(stmt)).scalar_one_or_none() is not None
    except (IntegrityError, PendingRollbackError):
        return False


async def run_financial_jobs(now: datetime | None = None, *, session_factory=None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    factory = session_factory or async_session_factory
    return {
        "invoices": await _run(factory, "subscription_billing", now, generate_subscription_invoices),
        "past_due": await _run(factory, "subscription_past_due", now, process_past_due),
        "holds": await _run(factory, "commission_hold_release", now, release_due_holds),
        "payouts": await _run_list(factory, "payout_generation", now, generate_due_payouts),
        "overdue": await _run(factory, "payout_overdue", now, mark_overdue_payouts),
        "reminders": await _run(factory, "payout_reminders", now, send_payout_notifications),
        "reconciliation": await _run(factory, "reconciliation", now, reconcile_open_transactions),
    }


async def _run(factory, name, now, func) -> int:
    return await _execute(factory, name, now.strftime("%Y%m%d%H%M")[:12], now, func, list_result=False)


async def _run_list(factory, name, now, func) -> int:
    return await _execute(factory, name, now.strftime("%Y%m%d%H"), now, func, list_result=True)


async def _execute(factory, name: str, key: str, now: datetime, func, *, list_result: bool) -> int:
    async with factory() as db:
        try:
            if not await _claim_lock(db, name, key):
                await db.rollback()
                return 0
            created = await func(db, now=now)
            await db.commit()
            if list_result:
                return len(created) if created is not None else 0
            return int(created or 0)
        except Exception:
            await db.rollback()
            logger.exception("financial_job_failed", job=name)
            return 0
