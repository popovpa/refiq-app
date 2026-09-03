from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import PromoGenerationItemStatus, PromoGenerationRunStatus
from app.core.config import settings
from app.core.exceptions import AppError
from app.modules.ai.application.creative.promo_kit import (
    build_offer_snapshot,
    create_slot_images,
    generate_brief_from_snapshot,
    generate_slot_payload,
    persist_slot_creative,
    promo_error_code,
    promo_error_message,
)
from app.modules.ai.jobs import GenerationJobRunner
from app.modules.creatives.promo_catalog import PromoSlot, QR_SLOT_ID, require_qr_tracking_link, resolve_slots
from app.modules.creatives.promo_runs import (
    ACTIVE_RUN_STATUSES,
    OfferPromoGenerationItem,
    OfferPromoGenerationRun,
    dump_run,
    get_active_run,
    list_run_items,
)
from app.modules.offers.models import Offer

logger = structlog.get_logger()

_inflight_runs: set[int] = set()


def _utc_age_seconds(started: datetime | None) -> float:
    if started is None:
        return 0.0
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - started).total_seconds()


async def start_promo_kit(
    db: AsyncSession,
    *,
    offer: Offer,
    user_id: int,
    job_runner: GenerationJobRunner | None,
    slots: list[str] | None = None,
    qr_tracking_link_id: int | None = None,
) -> dict:
    if job_runner is None:
        raise AppError("AI_UNAVAILABLE", "Async generation is not configured", 503)
    selected = resolve_slots(slots)
    qr_link = None
    if any(slot.kind == "qr_image" for slot in selected):
        qr_link = await require_qr_tracking_link(
            db, offer_id=offer.id, tracking_link_id=qr_tracking_link_id
        )
    existing = await get_active_run(db, offer.id)
    if existing:
        raise AppError("PROMO_GENERATION_IN_PROGRESS", "Promo generation is already running", 409)

    snapshot = await build_offer_snapshot(db, offer, user_id=user_id)
    run = OfferPromoGenerationRun(
        offer_id=offer.id,
        created_by_user_id=user_id,
        status=PromoGenerationRunStatus.QUEUED.value,
        total_items=len(selected),
        offer_snapshot=snapshot,
        promotion_brief=None,
        cancel_requested=False,
    )
    db.add(run)
    await db.flush()
    for slot in selected:
        item_result = None
        if slot.kind == "qr_image" and qr_link is not None:
            item_result = {"qr_tracking_link_id": qr_link.id, "short_code": qr_link.short_code}
        db.add(
            OfferPromoGenerationItem(
                generation_run_id=run.id,
                material_type=slot.id,
                channel=slot.channel,
                status=PromoGenerationItemStatus.QUEUED.value,
                result=item_result,
                progress=0,
            )
        )
    await db.commit()
    job_runner.submit(process_promo_run, run.id)
    return await dump_run(db, run)


async def process_promo_run(run_id: int) -> None:
    if run_id in _inflight_runs:
        return
    _inflight_runs.add(run_id)
    try:
        await _run_promo_job(run_id)
    finally:
        _inflight_runs.discard(run_id)


async def _run_promo_job(run_id: int) -> None:
    from app.modules.ai.deps import get_usage_session_factory

    factory = get_usage_session_factory()
    async with factory() as db:
        ready = await _ensure_brief(db, run_id)
        if not ready:
            return
        await db.commit()

    concurrency = max(1, int(settings.PROMO_GENERATION_CONCURRENCY or 1))
    while True:
        async with factory() as db:
            run = await db.get(OfferPromoGenerationRun, run_id)
            if run is None:
                return
            if run.cancel_requested:
                await _cancel_queued_items(db, run)
                await _refresh_counts(db, run)
                await _finalize_run(db, run)
                await db.commit()
                return
            batch_ids: list[int] = []
            for _ in range(concurrency):
                item = await _claim_next_item(db, run.id)
                if item is None:
                    break
                batch_ids.append(item.id)
            await db.commit()
            if not batch_ids:
                await _refresh_counts(db, run)
                idle = await _finalize_if_idle(db, run)
                await db.commit()
                if idle:
                    return
                await asyncio.sleep(0.2)
                continue
        if concurrency == 1:
            await _process_item(run_id, batch_ids[0])
        else:
            await asyncio.gather(*[_process_item(run_id, item_id) for item_id in batch_ids])


async def cancel_promo_run(db: AsyncSession, run: OfferPromoGenerationRun) -> OfferPromoGenerationRun:
    if run.status in {
        PromoGenerationRunStatus.COMPLETED.value,
        PromoGenerationRunStatus.COMPLETED_WITH_ERRORS.value,
        PromoGenerationRunStatus.FAILED.value,
        PromoGenerationRunStatus.CANCELLED.value,
    }:
        return run
    run.cancel_requested = True
    run.status = PromoGenerationRunStatus.CANCEL_REQUESTED.value
    await _cancel_queued_items(db, run)
    await _refresh_counts(db, run)
    generating = await _has_generating(db, run.id)
    if not generating:
        await _finalize_run(db, run)
    await db.commit()
    await db.refresh(run)
    return run


async def retry_promo_item(
    db: AsyncSession,
    *,
    run: OfferPromoGenerationRun,
    item: OfferPromoGenerationItem,
    job_runner: GenerationJobRunner | None,
) -> OfferPromoGenerationRun:
    if job_runner is None:
        raise AppError("AI_UNAVAILABLE", "Async generation is not configured", 503)
    if item.status not in {
        PromoGenerationItemStatus.FAILED.value,
        PromoGenerationItemStatus.CANCELLED.value,
    }:
        raise AppError("PROMO_ITEM_NOT_RETRYABLE", "Only failed or cancelled materials can be retried", 400)
    item.status = PromoGenerationItemStatus.QUEUED.value
    item.progress = 0
    item.error_code = None
    item.error_message = None
    item.started_at = None
    item.completed_at = None
    item.promo_material_id = None
    item.result = _qr_meta(item.result) or None
    run.cancel_requested = False
    run.completed_at = None
    run.dismissed_at = None
    run.status = PromoGenerationRunStatus.QUEUED.value
    await _refresh_counts(db, run)
    await db.commit()
    job_runner.submit(process_promo_run, run.id)
    await db.refresh(run)
    return run


async def ack_promo_run(db: AsyncSession, run: OfferPromoGenerationRun) -> OfferPromoGenerationRun:
    if run.status in ACTIVE_RUN_STATUSES:
        raise AppError("PROMO_GENERATION_IN_PROGRESS", "Generation is still running", 409)
    run.dismissed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def _ensure_brief(db: AsyncSession, run_id: int) -> bool | None:
    run = await db.get(OfferPromoGenerationRun, run_id)
    if run is None:
        return False
    if run.promotion_brief:
        if run.status == PromoGenerationRunStatus.QUEUED.value:
            run.status = PromoGenerationRunStatus.RUNNING.value
            run.started_at = run.started_at or datetime.now(timezone.utc)
        return True
    if run.cancel_requested:
        await _cancel_queued_items(db, run)
        await _finalize_run(db, run)
        await db.commit()
        return False
    if run.status == PromoGenerationRunStatus.RUNNING.value:
        started = run.started_at or run.created_at
        if _utc_age_seconds(started) < 90:
            return False
    run.status = PromoGenerationRunStatus.RUNNING.value
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    try:
        brief = await generate_brief_from_snapshot(
            snapshot=run.offer_snapshot or {},
            user_id=run.created_by_user_id,
            offer_id=run.offer_id,
            run_id=run.id,
        )
    except Exception as exc:
        logger.warning(
            "promo_brief_failed",
            run_id=run.id,
            error_type=type(exc).__name__,
            error_code=promo_error_code(exc),
            error_message=getattr(exc, "message", str(exc))[:300],
            provider_metadata=getattr(exc, "provider_metadata", None),
        )
        try:
            await _persist_brief_failure(
                run_id,
                promo_error_code(exc),
                promo_error_message(exc, "Promotion brief failed"),
            )
        except Exception:
            logger.exception("promo_brief_failure_persist_failed", run_id=run_id)
        return False

    run = await db.get(OfferPromoGenerationRun, run_id)
    if run is None:
        return False
    if run.cancel_requested:
        await _cancel_queued_items(db, run)
        await _finalize_run(db, run)
        await db.commit()
        return False
    run.promotion_brief = brief
    return True


async def _claim_next_item(db: AsyncSession, run_id: int) -> OfferPromoGenerationItem | None:
    now = datetime.now(timezone.utc)
    item_id = (
        await db.execute(
            select(OfferPromoGenerationItem.id)
            .where(
                OfferPromoGenerationItem.generation_run_id == run_id,
                OfferPromoGenerationItem.status == PromoGenerationItemStatus.QUEUED.value,
            )
            .order_by(OfferPromoGenerationItem.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if item_id is None:
        return None
    result = await db.execute(
        update(OfferPromoGenerationItem)
        .where(
            OfferPromoGenerationItem.id == item_id,
            OfferPromoGenerationItem.status == PromoGenerationItemStatus.QUEUED.value,
        )
        .values(
            status=PromoGenerationItemStatus.GENERATING.value,
            started_at=now,
            progress=10,
        )
        .returning(OfferPromoGenerationItem)
    )
    return result.scalar_one_or_none()


async def _process_item(run_id: int, item_id: int) -> None:
    from app.modules.ai.deps import get_usage_session_factory

    factory = get_usage_session_factory()
    async with factory() as db:
        run = await db.get(OfferPromoGenerationRun, run_id)
        item = await db.get(OfferPromoGenerationItem, item_id)
        if run is None or item is None:
            return
        if run.cancel_requested:
            item.status = PromoGenerationItemStatus.CANCELLED.value
            item.completed_at = datetime.now(timezone.utc)
            item.progress = 100
            await _refresh_counts(db, run)
            await _finalize_if_idle(db, run)
            await db.commit()
            return
        offer = (await db.execute(select(Offer).where(Offer.id == run.offer_id))).scalar_one_or_none()
        if offer is None:
            item.status = PromoGenerationItemStatus.FAILED.value
            item.error_code = "OFFER_NOT_FOUND"
            item.error_message = "Offer not found"
            item.completed_at = datetime.now(timezone.utc)
            item.progress = 100
            await _refresh_counts(db, run)
            await db.commit()
            return
        slot = resolve_slots([item.material_type])[0]
        item.progress = 40
        await db.commit()
        try:
            created_ids = await _generate_and_persist(db, run=run, item=item, offer=offer, slot=slot)
        except Exception as exc:
            await db.rollback()
            item = await db.get(OfferPromoGenerationItem, item_id)
            run = await db.get(OfferPromoGenerationRun, run_id)
            if item is None or run is None:
                return
            if run.cancel_requested:
                item.status = PromoGenerationItemStatus.CANCELLED.value
                item.error_code = None
                item.error_message = None
            else:
                item.status = PromoGenerationItemStatus.FAILED.value
                item.error_code = promo_error_code(exc)
                item.error_message = promo_error_message(exc, "Promo material generation failed")
            item.completed_at = datetime.now(timezone.utc)
            item.progress = 100
            await _refresh_counts(db, run)
            await _finalize_if_idle(db, run)
            await db.commit()
            logger.warning(
                "promo_item_failed",
                run_id=run_id,
                item_id=item_id,
                slot=item.material_type,
                error_type=type(exc).__name__,
                error_code=item.error_code,
                error_message=item.error_message,
                provider_metadata=getattr(exc, "provider_metadata", None),
            )
            return

        run = await db.get(OfferPromoGenerationRun, run_id)
        item = await db.get(OfferPromoGenerationItem, item_id)
        if run is None or item is None:
            return
        if run.cancel_requested:
            from app.modules.creatives.models import Creative
            from app.modules.creatives.service import CreativeService

            service = CreativeService(db)
            for creative_id in created_ids:
                creative = await db.get(Creative, creative_id)
                if creative:
                    await service.delete(creative)
            item.status = PromoGenerationItemStatus.CANCELLED.value
            item.promo_material_id = None
            item.result = None
            item.completed_at = datetime.now(timezone.utc)
            item.progress = 100
            await _refresh_counts(db, run)
            await _finalize_if_idle(db, run)
            await db.commit()
            return
        item.status = PromoGenerationItemStatus.COMPLETED.value
        item.promo_material_id = created_ids[0] if created_ids else None
        item.result = {**_qr_meta(item.result), "creative_ids": created_ids}
        item.completed_at = datetime.now(timezone.utc)
        item.progress = 100
        await _refresh_counts(db, run)
        await _finalize_if_idle(db, run)
        await db.commit()


async def _generate_and_persist(
    db: AsyncSession,
    *,
    run: OfferPromoGenerationRun,
    item: OfferPromoGenerationItem,
    offer: Offer,
    slot: PromoSlot,
) -> list[int]:
    context = {**(run.offer_snapshot or {}), "brief": run.promotion_brief or {}}
    brief = run.promotion_brief or {}
    if await _abort_requested(db, run.id, item.id):
        raise _Cancelled()
    if slot.kind in {"image", "qr_image"}:
        qr_meta = _qr_meta(item.result)
        creatives = await create_slot_images(
            db,
            offer=offer,
            user_id=run.created_by_user_id,
            context=context,
            brief=brief,
            slot=slot,
            generation_id=str(run.id),
            run_id=run.id,
            item_id=item.id,
            should_abort=lambda: _abort_requested(db, run.id, item.id),
            qr_tracking_link_id=qr_meta.get("qr_tracking_link_id"),
            qr_short_code=qr_meta.get("short_code"),
        )
        return [creative.id for creative in creatives]
    payload = await generate_slot_payload(
        offer_id=offer.id,
        user_id=run.created_by_user_id,
        context=context,
        brief=brief,
        slot=slot,
        run_id=run.id,
        item_id=item.id,
    )
    if await _abort_requested(db, run.id, item.id):
        raise _Cancelled()
    creative = await persist_slot_creative(
        db,
        offer=offer,
        user_id=run.created_by_user_id,
        slot=slot,
        payload=payload,
        generation_id=str(run.id),
    )
    await db.commit()
    return [creative.id]


async def _abort_requested(db: AsyncSession, run_id: int, item_id: int) -> bool:
    run = await db.get(OfferPromoGenerationRun, run_id)
    item = await db.get(OfferPromoGenerationItem, item_id)
    if run is None or item is None:
        return True
    return bool(run.cancel_requested)


async def _cancel_queued_items(db: AsyncSession, run: OfferPromoGenerationRun) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(OfferPromoGenerationItem)
        .where(
            OfferPromoGenerationItem.generation_run_id == run.id,
            OfferPromoGenerationItem.status == PromoGenerationItemStatus.QUEUED.value,
        )
        .values(
            status=PromoGenerationItemStatus.CANCELLED.value,
            completed_at=now,
            progress=100,
        )
    )


async def _fail_remaining_items(db: AsyncSession, run: OfferPromoGenerationRun, code: str, message: str) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(OfferPromoGenerationItem)
        .where(
            OfferPromoGenerationItem.generation_run_id == run.id,
            OfferPromoGenerationItem.status.in_(
                (
                    PromoGenerationItemStatus.QUEUED.value,
                    PromoGenerationItemStatus.GENERATING.value,
                )
            ),
        )
        .values(
            status=PromoGenerationItemStatus.FAILED.value,
            error_code=code,
            error_message=message,
            completed_at=now,
            progress=100,
        )
    )


async def _persist_brief_failure(run_id: int, code: str, message: str) -> None:
    from app.modules.ai.deps import get_usage_session_factory

    factory = get_usage_session_factory()
    async with factory() as db:
        run = await db.get(OfferPromoGenerationRun, run_id)
        if run is None:
            return
        if run.cancel_requested:
            await _cancel_queued_items(db, run)
            await _finalize_run(db, run)
            await db.commit()
            return
        now = datetime.now(timezone.utc)
        await db.execute(
            update(OfferPromoGenerationRun)
            .where(OfferPromoGenerationRun.id == run_id)
            .values(
                status=PromoGenerationRunStatus.FAILED.value,
                completed_at=now,
            )
        )
        await _fail_remaining_items(db, run, code, message)
        await _refresh_counts(db, run)
        await db.commit()


async def _refresh_counts(db: AsyncSession, run: OfferPromoGenerationRun) -> None:
    items = await list_run_items(db, run.id)
    completed = sum(1 for item in items if item.status == PromoGenerationItemStatus.COMPLETED.value)
    failed = sum(1 for item in items if item.status == PromoGenerationItemStatus.FAILED.value)
    cancelled = sum(1 for item in items if item.status == PromoGenerationItemStatus.CANCELLED.value)
    await db.execute(
        update(OfferPromoGenerationRun)
        .where(OfferPromoGenerationRun.id == run.id)
        .values(
            completed_items=completed,
            failed_items=failed,
            cancelled_items=cancelled,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.refresh(run)


async def _has_generating(db: AsyncSession, run_id: int) -> bool:
    item = (
        await db.execute(
            select(OfferPromoGenerationItem.id)
            .where(
                OfferPromoGenerationItem.generation_run_id == run_id,
                OfferPromoGenerationItem.status == PromoGenerationItemStatus.GENERATING.value,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return item is not None


async def _finalize_if_idle(db: AsyncSession, run: OfferPromoGenerationRun) -> bool:
    queued = (
        await db.execute(
            select(OfferPromoGenerationItem.id)
            .where(
                OfferPromoGenerationItem.generation_run_id == run.id,
                OfferPromoGenerationItem.status.in_(
                    (
                        PromoGenerationItemStatus.QUEUED.value,
                        PromoGenerationItemStatus.GENERATING.value,
                    )
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if queued is not None:
        return False
    await _finalize_run(db, run)
    return True


async def _finalize_run(db: AsyncSession, run: OfferPromoGenerationRun) -> None:
    await _refresh_counts(db, run)
    if run.cancel_requested:
        run.status = PromoGenerationRunStatus.CANCELLED.value
    elif run.failed_items and run.completed_items == 0 and run.cancelled_items == run.total_items - run.failed_items:
        run.status = PromoGenerationRunStatus.COMPLETED_WITH_ERRORS.value
    elif run.failed_items:
        run.status = PromoGenerationRunStatus.COMPLETED_WITH_ERRORS.value
    elif run.completed_items == 0 and run.cancelled_items:
        run.status = PromoGenerationRunStatus.CANCELLED.value
    elif run.completed_items == 0:
        run.status = PromoGenerationRunStatus.FAILED.value
    else:
        run.status = PromoGenerationRunStatus.COMPLETED.value
    run.completed_at = datetime.now(timezone.utc)


def _qr_meta(result: dict | None) -> dict:
    if not isinstance(result, dict):
        return {}
    meta = {}
    link_id = result.get("qr_tracking_link_id")
    if link_id is not None:
        try:
            meta["qr_tracking_link_id"] = int(link_id)
        except (TypeError, ValueError):
            pass
    short_code = str(result.get("short_code") or "").strip()
    if short_code:
        meta["short_code"] = short_code
    return meta


class _Cancelled(Exception):
    pass


async def pump_queued_runs() -> None:
    from app.modules.ai.deps import get_usage_session_factory

    factory = get_usage_session_factory()
    async with factory() as db:
        rows = (
            await db.execute(
                select(OfferPromoGenerationRun.id).where(
                    OfferPromoGenerationRun.status.in_(tuple(ACTIVE_RUN_STATUSES))
                )
            )
        ).scalars().all()
    for run_id in rows:
        try:
            await process_promo_run(run_id)
        except Exception:
            logger.exception("promo_run_pump_failed", run_id=run_id)
