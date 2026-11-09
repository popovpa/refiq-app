from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import DestinationStatus, DestinationType
from app.core.exceptions import AppError, NotFoundError
from app.modules.links.destination import assert_destination_allowed
from app.modules.links.models import TrackingLink
from app.modules.offers.destination_compliance import (
    assert_destination_compliance,
    destination_compliance_block,
)
from app.modules.offers.destination_model import OfferDestination
from app.modules.offers.destination_url import validate_destination_image_url, validate_destination_page_url
from app.modules.offers.models import Offer
from app.modules.products.models import Product

SNAPSHOT_WARNING = (
    "Уже созданные ссылки сохраняют предыдущий URL. Новый адрес используется только для новых ссылок."
)
DESTINATION_TYPES = {item.value for item in DestinationType}
DESTINATION_STATUSES = {item.value for item in DestinationStatus}


def serialize_destination(destination: OfferDestination, *, links_count: int = 0, public: bool = False) -> dict:
    payload = {
        "id": destination.id,
        "offer_id": destination.offer_id,
        "title": destination.title,
        "url": destination.url,
        "type": destination.type,
        "image_url": destination.image_url,
        "is_primary": bool(destination.is_primary),
        "status": destination.status,
        "available": destination.status == DestinationStatus.ACTIVE.value,
    }
    if public:
        return payload
    payload.update(
        {
            "sort_order": destination.sort_order,
            "links_count": links_count,
            "created_at": destination.created_at.isoformat() if destination.created_at else None,
            "updated_at": destination.updated_at.isoformat() if destination.updated_at else None,
        }
    )
    return payload


async def _product_for_offer(db: AsyncSession, offer: Offer) -> Product | None:
    if not offer.product_id:
        return None
    return (await db.execute(select(Product).where(Product.id == offer.product_id))).scalar_one_or_none()


async def destination_count(db: AsyncSession, offer_id: int) -> int:
    return int(
        await db.scalar(select(func.count(OfferDestination.id)).where(OfferDestination.offer_id == offer_id)) or 0
    )


async def active_primary(db: AsyncSession, offer_id: int) -> OfferDestination | None:
    return (
        await db.execute(
            select(OfferDestination).where(
                OfferDestination.offer_id == offer_id,
                OfferDestination.is_primary.is_(True),
                OfferDestination.status == DestinationStatus.ACTIVE.value,
            )
        )
    ).scalar_one_or_none()


async def legacy_skip_reason(db: AsyncSession, offer: Offer) -> str | None:
    product = await _product_for_offer(db, offer)
    url = (product.url or "").strip() if product and product.url else ""
    if not url:
        return "missing_url"
    block = destination_compliance_block(offer)
    if block:
        return block
    try:
        normalized = await validate_destination_page_url(url)
        await assert_destination_allowed(db, business_id=offer.business_id, url=normalized)
    except AppError as exc:
        return exc.code
    return None


async def ensure_legacy_primary_destination(db: AsyncSession, offer: Offer) -> str:
    """Create one primary page from Product.url when it is safe. Idempotent."""
    if await destination_count(db, offer.id):
        return "exists"
    reason = await legacy_skip_reason(db, offer)
    if reason:
        return reason
    product = await _product_for_offer(db, offer)
    assert product is not None and product.url
    normalized = await validate_destination_page_url(product.url)
    normalized = await assert_destination_allowed(db, business_id=offer.business_id, url=normalized)
    title = (product.name or offer.name or "Основная страница").strip()[:255] or "Основная страница"
    destination = OfferDestination(
        offer_id=offer.id,
        title=title,
        url=normalized,
        type=DestinationType.PRODUCT.value,
        image_url=None,
        status=DestinationStatus.ACTIVE.value,
        is_primary=True,
        sort_order=0,
    )
    db.add(destination)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        return "exists"
    return "created"


async def backfill_legacy_destinations(db: AsyncSession) -> dict:
    offers = (await db.execute(select(Offer).order_by(Offer.id))).scalars().all()
    created = 0
    skipped: list[dict] = []
    for offer in offers:
        try:
            result = await ensure_legacy_primary_destination(db, offer)
        except IntegrityError:
            result = "exists"
        if result == "created":
            created += 1
        elif result != "exists":
            product = await _product_for_offer(db, offer)
            skipped.append(
                {
                    "offer_id": offer.id,
                    "url": product.url if product else None,
                    "reason": result,
                }
            )
    return {"created": created, "skipped": skipped}


async def _links_count_map(db: AsyncSession, offer_id: int) -> dict[int, int]:
    rows = (
        await db.execute(
            select(TrackingLink.offer_destination_id, func.count(TrackingLink.id))
            .where(
                TrackingLink.offer_id == offer_id,
                TrackingLink.offer_destination_id.is_not(None),
            )
            .group_by(TrackingLink.offer_destination_id)
        )
    ).all()
    return {destination_id: int(count) for destination_id, count in rows if destination_id is not None}


async def list_destinations(
    db: AsyncSession,
    offer: Offer,
    *,
    status: str | None = None,
    destination_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
    public: bool = False,
    materialize_legacy: bool = True,
) -> dict:
    if materialize_legacy:
        await ensure_legacy_primary_destination(db, offer)
    filters = [OfferDestination.offer_id == offer.id]
    if public:
        filters.append(OfferDestination.status == DestinationStatus.ACTIVE.value)
    elif status:
        if status not in DESTINATION_STATUSES:
            raise AppError("INVALID_DESTINATION_STATUS", "Некорректный статус страницы", 400)
        filters.append(OfferDestination.status == status)
    if destination_type:
        if destination_type not in DESTINATION_TYPES:
            raise AppError("INVALID_DESTINATION_TYPE", "Некорректный тип страницы", 400)
        filters.append(OfferDestination.type == destination_type)
    total = int(await db.scalar(select(func.count(OfferDestination.id)).where(*filters)) or 0)
    rows = (
        await db.execute(
            select(OfferDestination)
            .where(*filters)
            .order_by(OfferDestination.is_primary.desc(), OfferDestination.sort_order.asc(), OfferDestination.id.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()
    counts = {} if public else await _links_count_map(db, offer.id)
    payload = {
        "items": [serialize_destination(row, links_count=counts.get(row.id, 0), public=public) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
    if not public and total == 0:
        product = await _product_for_offer(db, offer)
        payload["legacy_product_url"] = product.url if product else None
        payload["legacy_skip_reason"] = await legacy_skip_reason(db, offer) if product and product.url else None
    return payload


async def _get_destination(db: AsyncSession, offer_id: int, destination_id: int) -> OfferDestination:
    destination = (
        await db.execute(
            select(OfferDestination).where(
                OfferDestination.id == destination_id,
                OfferDestination.offer_id == offer_id,
            )
        )
    ).scalar_one_or_none()
    if not destination:
        raise NotFoundError("Destination")
    return destination


async def _clear_other_primaries(db: AsyncSession, offer_id: int, keep_id: int | None) -> None:
    stmt = update(OfferDestination).where(OfferDestination.offer_id == offer_id, OfferDestination.is_primary.is_(True))
    if keep_id is not None:
        stmt = stmt.where(OfferDestination.id != keep_id)
    await db.execute(stmt.values(is_primary=False))


async def _next_sort_order(db: AsyncSession, offer_id: int) -> int:
    current = await db.scalar(select(func.max(OfferDestination.sort_order)).where(OfferDestination.offer_id == offer_id))
    return int(current or 0) + 1


def _same_page(existing: OfferDestination, *, title: str, destination_type: str, image_url: str | None, is_primary: bool) -> bool:
    return (
        existing.title == title
        and existing.type == destination_type
        and existing.image_url == image_url
        and (not is_primary or existing.is_primary)
    )


async def create_destination(
    db: AsyncSession,
    offer: Offer,
    *,
    title: str,
    url: str,
    destination_type: str,
    image_url: str | None,
    is_primary: bool,
) -> tuple[OfferDestination, bool]:
    assert_destination_compliance(offer)
    if destination_type not in DESTINATION_TYPES:
        raise AppError("INVALID_DESTINATION_TYPE", "Некорректный тип страницы", 400)
    normalized = await validate_destination_page_url(url)
    normalized = await assert_destination_allowed(db, business_id=offer.business_id, url=normalized)
    image = await validate_destination_image_url(image_url)
    clean_title = title.strip()
    if not clean_title:
        raise AppError("INVALID_DESTINATION_TITLE", "Укажите название страницы", 400)
    existing = (
        await db.execute(
            select(OfferDestination).where(
                OfferDestination.offer_id == offer.id,
                OfferDestination.url == normalized,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if existing.status == DestinationStatus.ACTIVE.value and _same_page(
            existing,
            title=clean_title,
            destination_type=destination_type,
            image_url=image,
            is_primary=is_primary,
        ):
            return existing, False
        raise AppError("DESTINATION_DUPLICATE", "Такая страница уже добавлена в оффер.", 409)
    make_primary = is_primary or await destination_count(db, offer.id) == 0
    if make_primary:
        await _clear_other_primaries(db, offer.id, None)
    destination = OfferDestination(
        offer_id=offer.id,
        title=clean_title[:255],
        url=normalized,
        type=destination_type,
        image_url=image,
        status=DestinationStatus.ACTIVE.value,
        is_primary=make_primary,
        sort_order=await _next_sort_order(db, offer.id),
    )
    db.add(destination)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise AppError("DESTINATION_CONFLICT", "Не удалось сохранить страницу. Повторите действие.", 409) from exc
    await db.refresh(destination)
    if make_primary:
        await _sync_product_url(db, offer, normalized)
    return destination, True


async def _sync_product_url(db: AsyncSession, offer: Offer, url: str) -> None:
    product = await _product_for_offer(db, offer)
    if product is not None:
        product.url = url


async def snapshot_warning(db: AsyncSession, offer_id: int) -> str | None:
    count = int(await db.scalar(select(func.count(TrackingLink.id)).where(TrackingLink.offer_id == offer_id)) or 0)
    if count:
        return SNAPSHOT_WARNING
    return None


async def update_destination(
    db: AsyncSession,
    offer: Offer,
    destination_id: int,
    changes: dict,
) -> tuple[OfferDestination, str | None]:
    destination = await _get_destination(db, offer.id, destination_id)
    warning = None
    if "title" in changes and changes["title"] is not None:
        title = changes["title"].strip()
        if not title:
            raise AppError("INVALID_DESTINATION_TITLE", "Укажите название страницы", 400)
        destination.title = title[:255]
    if "type" in changes and changes["type"] is not None:
        if changes["type"] not in DESTINATION_TYPES:
            raise AppError("INVALID_DESTINATION_TYPE", "Некорректный тип страницы", 400)
        destination.type = changes["type"]
    if "image_url" in changes:
        destination.image_url = await validate_destination_image_url(changes["image_url"])
    if "sort_order" in changes and changes["sort_order"] is not None:
        if int(changes["sort_order"]) < 0:
            raise AppError("INVALID_SORT_ORDER", "Порядок не может быть отрицательным", 400)
        destination.sort_order = int(changes["sort_order"])
    if "url" in changes and changes["url"] is not None:
        assert_destination_compliance(offer)
        normalized = await validate_destination_page_url(changes["url"])
        normalized = await assert_destination_allowed(db, business_id=offer.business_id, url=normalized)
        duplicate = (
            await db.execute(
                select(OfferDestination.id).where(
                    OfferDestination.offer_id == offer.id,
                    OfferDestination.url == normalized,
                    OfferDestination.id != destination.id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise AppError("DESTINATION_DUPLICATE", "Такая страница уже добавлена в оффер.", 409)
        if destination.url != normalized:
            destination.url = normalized
            warning = await snapshot_warning(db, offer.id)
            if destination.is_primary:
                await _sync_product_url(db, offer, normalized)
    if "status" in changes and changes["status"] is not None:
        status = changes["status"]
        if status not in DESTINATION_STATUSES:
            raise AppError("INVALID_DESTINATION_STATUS", "Некорректный статус страницы", 400)
        if status == DestinationStatus.DISABLED.value and destination.status != status:
            await _disable_destination(db, offer, destination, changes.get("replacement_primary_id"))
        elif status == DestinationStatus.ACTIVE.value and destination.status != status:
            assert_destination_compliance(offer)
            destination.status = DestinationStatus.ACTIVE.value
            await _ensure_some_primary(db, offer.id, destination)
    if changes.get("is_primary") is True:
        if destination.status != DestinationStatus.ACTIVE.value:
            raise AppError("DESTINATION_UNAVAILABLE", "Отключённую страницу нельзя сделать основной.", 400)
        await _clear_other_primaries(db, offer.id, destination.id)
        destination.is_primary = True
        await _sync_product_url(db, offer, destination.url)
    elif changes.get("is_primary") is False and destination.is_primary:
        replacement = changes.get("replacement_primary_id")
        if replacement is None:
            raise AppError(
                "PRIMARY_REPLACEMENT_REQUIRED",
                "Выберите другую активную основную страницу.",
                409,
            )
        await _assign_primary(db, offer, int(replacement), current_id=destination.id)
        destination.is_primary = False
    try:
        await db.flush()
    except IntegrityError as exc:
        raise AppError("PRIMARY_CONFLICT", "Основная страница уже назначена. Повторите действие.", 409) from exc
    await db.refresh(destination)
    return destination, warning


async def _assign_primary(db: AsyncSession, offer: Offer, destination_id: int, *, current_id: int | None) -> OfferDestination:
    replacement = await _get_destination(db, offer.id, destination_id)
    if current_id is not None and replacement.id == current_id:
        raise AppError("PRIMARY_REPLACEMENT_REQUIRED", "Выберите другую активную страницу.", 409)
    if replacement.status != DestinationStatus.ACTIVE.value:
        raise AppError("DESTINATION_UNAVAILABLE", "Основной можно назначить только активную страницу.", 400)
    await _clear_other_primaries(db, offer.id, replacement.id)
    replacement.is_primary = True
    await _sync_product_url(db, offer, replacement.url)
    return replacement


async def _disable_destination(
    db: AsyncSession,
    offer: Offer,
    destination: OfferDestination,
    replacement_primary_id: int | None,
) -> None:
    if destination.is_primary:
        others = (
            await db.execute(
                select(OfferDestination.id).where(
                    OfferDestination.offer_id == offer.id,
                    OfferDestination.id != destination.id,
                    OfferDestination.status == DestinationStatus.ACTIVE.value,
                )
            )
        ).scalars().all()
        if others:
            if replacement_primary_id is None:
                raise AppError(
                    "PRIMARY_REPLACEMENT_REQUIRED",
                    "Выберите другую активную основную страницу.",
                    409,
                )
            if int(replacement_primary_id) not in set(others):
                raise AppError("PRIMARY_REPLACEMENT_REQUIRED", "Выберите другую активную страницу этого оффера.", 409)
            await _assign_primary(db, offer, int(replacement_primary_id), current_id=destination.id)
        destination.is_primary = False
    destination.status = DestinationStatus.DISABLED.value


async def _ensure_some_primary(db: AsyncSession, offer_id: int, destination: OfferDestination) -> None:
    current = await active_primary(db, offer_id)
    if current is None:
        destination.is_primary = True


async def disable_destination(
    db: AsyncSession,
    offer: Offer,
    destination_id: int,
    replacement_primary_id: int | None = None,
) -> OfferDestination:
    destination, _warning = await update_destination(
        db,
        offer,
        destination_id,
        {"status": DestinationStatus.DISABLED.value, "replacement_primary_id": replacement_primary_id},
    )
    return destination


async def lock_active_destination(db: AsyncSession, offer_id: int, destination_id: int) -> OfferDestination:
    destination = (
        await db.execute(select(OfferDestination).where(OfferDestination.id == destination_id))
    ).scalar_one_or_none()
    if not destination or destination.offer_id != offer_id:
        raise AppError("DESTINATION_UNAVAILABLE", "Посадочная страница недоступна.", 404)
    if destination.status != DestinationStatus.ACTIVE.value:
        raise AppError("DESTINATION_UNAVAILABLE", "Посадочная страница отключена.", 400)
    return destination


async def resolve_tracking_destination(
    db: AsyncSession,
    offer: Offer,
    *,
    offer_destination_id: int | None,
    destination_url: str | None,
    allow_explicit_url: bool,
) -> tuple[str, int | None]:
    if offer_destination_id is not None:
        assert_destination_compliance(offer)
        destination = await lock_active_destination(db, offer.id, offer_destination_id)
        url = await assert_destination_allowed(db, business_id=offer.business_id, url=destination.url)
        return url, destination.id
    explicit = (str(destination_url).strip() if destination_url else "") or None
    if explicit:
        if not allow_explicit_url:
            raise AppError("DESTINATION_URL_FORBIDDEN", "Партнёр не может указать произвольный URL.", 403)
        return await assert_destination_allowed(db, business_id=offer.business_id, url=explicit), None
    try:
        await ensure_legacy_primary_destination(db, offer)
    except IntegrityError:
        pass
    primary = await active_primary(db, offer.id)
    if primary:
        assert_destination_compliance(offer)
        url = await assert_destination_allowed(db, business_id=offer.business_id, url=primary.url)
        return url, primary.id
    if await destination_count(db, offer.id):
        raise AppError("DESTINATION_UNAVAILABLE", "Нет активной посадочной страницы.", 400)
    from app.modules.offers.service import product_url_for_offer

    legacy = await product_url_for_offer(db, offer)
    if not legacy:
        raise AppError("OFFER_LANDING_MISSING", "Для оффера не задана страница продукта", 400)
    return await assert_destination_allowed(db, business_id=offer.business_id, url=legacy), None


async def apply_product_url_change(db: AsyncSession, offer: Offer, new_url: str | None) -> str | None:
    product = await _product_for_offer(db, offer)
    primary = (
        await db.execute(
            select(OfferDestination).where(
                OfferDestination.offer_id == offer.id,
                OfferDestination.is_primary.is_(True),
            )
        )
    ).scalar_one_or_none()
    if primary is None:
        if product is not None:
            product.url = new_url
        try:
            await ensure_legacy_primary_destination(db, offer)
        except IntegrityError:
            pass
        return None
    assert_destination_compliance(offer)
    normalized = await validate_destination_page_url(new_url or "")
    normalized = await assert_destination_allowed(db, business_id=offer.business_id, url=normalized)
    changed = primary.url != normalized
    primary.url = normalized
    if product is not None:
        product.url = normalized
    if not changed:
        return None
    return await snapshot_warning(db, offer.id)


async def assert_destination_allows_link_activation(db: AsyncSession, link: TrackingLink) -> None:
    if not link.offer_destination_id:
        return
    destination = (
        await db.execute(select(OfferDestination).where(OfferDestination.id == link.offer_destination_id))
    ).scalar_one_or_none()
    if (
        not destination
        or destination.offer_id != link.offer_id
        or destination.status != DestinationStatus.ACTIVE.value
    ):
        raise AppError("DESTINATION_UNAVAILABLE", "Посадочная страница отключена.", 400)


async def labels_for_destination_ids(db: AsyncSession, destination_ids: list[int]) -> dict[int, dict]:
    ids = [item for item in destination_ids if item]
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(OfferDestination.id, OfferDestination.title, OfferDestination.type).where(
                OfferDestination.id.in_(ids)
            )
        )
    ).all()
    return {
        row.id: {"destination_title": row.title, "destination_type": row.type}
        for row in rows
    }
