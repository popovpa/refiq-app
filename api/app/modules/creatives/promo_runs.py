from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import PromoGenerationItemStatus, PromoGenerationRunStatus
from app.core.database import Base
from app.core.ids import EntityId, fk_column, pk_column
from app.modules.creatives.promo_catalog import SLOTS

ACTIVE_RUN_STATUSES = {
    PromoGenerationRunStatus.QUEUED.value,
    PromoGenerationRunStatus.RUNNING.value,
    PromoGenerationRunStatus.CANCEL_REQUESTED.value,
}
TERMINAL_RUN_STATUSES = {
    PromoGenerationRunStatus.COMPLETED.value,
    PromoGenerationRunStatus.COMPLETED_WITH_ERRORS.value,
    PromoGenerationRunStatus.CANCELLED.value,
    PromoGenerationRunStatus.FAILED.value,
}
ITEM_PROCESSED_STATUSES = {
    PromoGenerationItemStatus.COMPLETED.value,
    PromoGenerationItemStatus.FAILED.value,
    PromoGenerationItemStatus.CANCELLED.value,
}


class OfferPromoGenerationRun(Base):
    __tablename__ = "offer_promo_generation_runs"

    id: Mapped[int] = pk_column()
    offer_id: Mapped[int] = fk_column("offers.id")
    created_by_user_id: Mapped[int] = fk_column("users.id")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PromoGenerationRunStatus.QUEUED.value, index=True
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offer_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    promotion_brief: Mapped[dict | None] = mapped_column(JSONB)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OfferPromoGenerationItem(Base):
    __tablename__ = "offer_promo_generation_items"

    id: Mapped[int] = pk_column()
    generation_run_id: Mapped[int] = mapped_column(
        ForeignKey("offer_promo_generation_runs.id"), nullable=False, index=True
    )
    material_type: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PromoGenerationItemStatus.QUEUED.value, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    promo_material_id: Mapped[int | None] = mapped_column(
        EntityId, ForeignKey("creatives.id", ondelete="SET NULL"), nullable=True, index=True
    )
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_item(item: OfferPromoGenerationItem) -> dict:
    slot = SLOTS.get(item.material_type)
    material_ids = []
    if item.result and item.result.get("creative_ids"):
        material_ids = [int(value) for value in item.result["creative_ids"]]
    elif item.promo_material_id:
        material_ids = [item.promo_material_id]
    return {
        "id": item.id,
        "generation_run_id": item.generation_run_id,
        "material_type": item.material_type,
        "channel": item.channel,
        "label": slot.label if slot else item.material_type,
        "group": slot.group if slot else "text",
        "status": item.status,
        "progress": item.progress,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "promo_material_id": item.promo_material_id,
        "material_ids": material_ids,
        "created_at": _iso(item.created_at),
        "started_at": _iso(item.started_at),
        "completed_at": _iso(item.completed_at),
    }


async def detach_creative_from_runs(db: AsyncSession, *, offer_id: int, creative_id: int) -> None:
    items = (
        await db.execute(
            select(OfferPromoGenerationItem)
            .join(
                OfferPromoGenerationRun,
                OfferPromoGenerationItem.generation_run_id == OfferPromoGenerationRun.id,
            )
            .where(OfferPromoGenerationRun.offer_id == offer_id)
        )
    ).scalars().all()
    for item in items:
        if item.promo_material_id == creative_id:
            item.promo_material_id = None
        ids = [int(value) for value in ((item.result or {}).get("creative_ids") or [])]
        if creative_id not in ids:
            continue
        payload = dict(item.result or {})
        payload["creative_ids"] = [value for value in ids if value != creative_id]
        item.result = payload


async def dump_run(db: AsyncSession, run: OfferPromoGenerationRun) -> dict:
    await db.refresh(run)
    items = await list_run_items(db, run.id)
    return serialize_run(run, items)


def serialize_run(run: OfferPromoGenerationRun, items: list[OfferPromoGenerationItem]) -> dict:
    processed = run.completed_items + run.failed_items + run.cancelled_items
    percentage = 0
    if run.total_items:
        percentage = int(round(100 * processed / run.total_items))
    created_ids: list[int] = []
    errors: list[dict] = []
    for item in items:
        payload = serialize_item(item)
        created_ids.extend(payload["material_ids"])
        if item.status == PromoGenerationItemStatus.FAILED.value:
            errors.append(
                {
                    "item_id": item.id,
                    "slot": item.material_type,
                    "code": item.error_code,
                    "message": item.error_message,
                }
            )
    return {
        "id": run.id,
        "run_id": run.id,
        "generation_id": str(run.id),
        "offer_id": run.offer_id,
        "status": run.status,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
        "failed_items": run.failed_items,
        "cancelled_items": run.cancelled_items,
        "processed_items": processed,
        "percentage": percentage,
        "cancel_requested": run.cancel_requested,
        "items": [serialize_item(item) for item in items],
        "created_ids": created_ids,
        "errors": errors,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "updated_at": _iso(run.updated_at),
    }


async def list_run_items(db: AsyncSession, run_id: int) -> list[OfferPromoGenerationItem]:
    result = await db.execute(
        select(OfferPromoGenerationItem)
        .where(OfferPromoGenerationItem.generation_run_id == run_id)
        .order_by(OfferPromoGenerationItem.id)
    )
    return list(result.scalars().all())


async def get_offer_run(
    db: AsyncSession, offer_id: int, run_id: int
) -> OfferPromoGenerationRun | None:
    return (
        await db.execute(
            select(OfferPromoGenerationRun).where(
                OfferPromoGenerationRun.id == run_id,
                OfferPromoGenerationRun.offer_id == offer_id,
            )
        )
    ).scalar_one_or_none()


async def get_visible_run(db: AsyncSession, offer_id: int) -> OfferPromoGenerationRun | None:
    result = await db.execute(
        select(OfferPromoGenerationRun)
        .where(
            OfferPromoGenerationRun.offer_id == offer_id,
            OfferPromoGenerationRun.dismissed_at.is_(None),
        )
        .order_by(OfferPromoGenerationRun.id.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None
    if run.status in ACTIVE_RUN_STATUSES:
        return run
    if run.status in TERMINAL_RUN_STATUSES:
        return run
    return None


async def get_active_run(db: AsyncSession, offer_id: int) -> OfferPromoGenerationRun | None:
    result = await db.execute(
        select(OfferPromoGenerationRun)
        .where(
            OfferPromoGenerationRun.offer_id == offer_id,
            OfferPromoGenerationRun.status.in_(tuple(ACTIVE_RUN_STATUSES)),
        )
        .order_by(OfferPromoGenerationRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
