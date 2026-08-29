from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CreativeSource, CreativeStatus, CreativeType
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.ai.application.creative.generate import (
    generate_creative,
    rewrite_creative,
)
from app.modules.ai.application.creative.promo_kit import regenerate_promo_material, start_promo_kit
from app.modules.ai.application.creative.promo_worker import ack_promo_run, cancel_promo_run, retry_promo_item
from app.modules.ai.jobs import get_job_runner
from app.modules.ai.lifecycle.service import AiGenerationService
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.creatives.access import get_business_offer
from app.modules.creatives.normalize import normalize_channel, normalize_format, normalize_type
from app.modules.creatives.promo_catalog import catalog_payload, is_qr_promo
from app.modules.creatives.qr_compose import compose_tracking_qr
from app.modules.creatives.promo_runs import (
    dump_run,
    get_offer_run,
    get_visible_run,
    list_run_items,
    serialize_run,
)
from app.modules.creatives.serialize import serialize_creative
from app.modules.creatives.service import CreativeService

router = APIRouter()


class GenerateCreativeRequest(BaseModel):
    type: str
    channel: str | None = None
    format: str | None = None
    instruction: str = Field(default="", max_length=4000)
    variants: int | None = None
    language: str | None = None
    goal: str | None = None
    style: str | None = None


class SaveCreativeRequest(BaseModel):
    generation_id: str | None = None
    variant_index: int = 0
    type: str | None = None
    channel: str | None = None
    format: str | None = None
    title: str | None = None
    headline: str | None = None
    body: str | None = None
    cta: str | None = None
    hashtags: list[str] | None = None
    language: str | None = None


class UpdateCreativeRequest(BaseModel):
    title: str | None = None
    headline: str | None = None
    body: str | None = None
    cta: str | None = None
    hashtags: list[str] | None = None


class RewriteCreativeRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)


class PromoKitRequest(BaseModel):
    slots: list[str] | None = None
    qr_tracking_link_id: int | None = None


@router.get("/{offer_id}/creatives")
async def list_creatives(
    offer_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    items = await CreativeService(db).list_for_business(offer)
    return {"items": [await _with_asset(db, offer_id, item) for item in items]}


@router.get("/{offer_id}/creatives/{creative_id}")
async def get_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    creative = await CreativeService(db).get_for_business(offer, parse_id(creative_id))
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/generate")
async def generate_offer_creative(
    offer_id: str,
    data: GenerateCreativeRequest,
    background_tasks: BackgroundTasks,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    return await generate_creative(
        db,
        offer=offer,
        user_id=parse_id(session_data["user_id"]),
        creative_type=normalize_type(data.type),
        instruction=data.instruction,
        variants=data.variants,
        channel=normalize_channel(data.channel),
        image_format=normalize_format(data.format),
        language=data.language,
        goal=data.goal,
        style=data.style,
        job_runner=get_job_runner(background_tasks),
    )


@router.post("/{offer_id}/creatives/promo-kit")
async def generate_promo_kit(
    offer_id: str,
    background_tasks: BackgroundTasks,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
    data: PromoKitRequest | None = None,
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    payload = await start_promo_kit(
        db,
        offer=offer,
        user_id=parse_id(session_data["user_id"]),
        job_runner=get_job_runner(background_tasks),
        slots=data.slots if data else None,
        qr_tracking_link_id=data.qr_tracking_link_id if data else None,
    )
    return JSONResponse(status_code=202, content=payload)


@router.get("/{offer_id}/promo-generation-catalog")
async def get_promo_generation_catalog(
    offer_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    return catalog_payload()


@router.get("/{offer_id}/promo-generation-runs/active")
async def get_active_promo_generation_run(
    offer_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    run = await get_visible_run(db, offer.id)
    if run is None:
        return {"run": None}
    items = await list_run_items(db, run.id)
    return {"run": serialize_run(run, items)}


@router.get("/{offer_id}/promo-generation-runs/{run_id}")
async def get_promo_generation_run(
    offer_id: str,
    run_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    run = await get_offer_run(db, offer.id, parse_id(run_id))
    if run is None:
        raise NotFoundError("Generation")
    items = await list_run_items(db, run.id)
    return serialize_run(run, items)


@router.post("/{offer_id}/promo-generation-runs/{run_id}/cancel")
async def cancel_promo_generation_run(
    offer_id: str,
    run_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    run = await get_offer_run(db, offer.id, parse_id(run_id))
    if run is None:
        raise NotFoundError("Generation")
    run = await cancel_promo_run(db, run)
    return await dump_run(db, run)


@router.post("/{offer_id}/promo-generation-runs/{run_id}/ack")
async def ack_promo_generation_run(
    offer_id: str,
    run_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    run = await get_offer_run(db, offer.id, parse_id(run_id))
    if run is None:
        raise NotFoundError("Generation")
    run = await ack_promo_run(db, run)
    return await dump_run(db, run)


@router.post("/{offer_id}/promo-generation-runs/{run_id}/items/{item_id}/retry")
async def retry_promo_generation_item(
    offer_id: str,
    run_id: str,
    item_id: str,
    background_tasks: BackgroundTasks,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    run = await get_offer_run(db, offer.id, parse_id(run_id))
    if run is None:
        raise NotFoundError("Generation")
    from app.modules.creatives.promo_runs import OfferPromoGenerationItem

    item = await db.get(OfferPromoGenerationItem, parse_id(item_id))
    if item is None or item.generation_run_id != run.id:
        raise NotFoundError("Generation")
    run = await retry_promo_item(
        db,
        run=run,
        item=item,
        job_runner=get_job_runner(background_tasks),
    )
    return await dump_run(db, run)


@router.post("/{offer_id}/creatives")
async def create_creative(
    offer_id: str,
    data: SaveCreativeRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    user_id = parse_id(session_data["user_id"])
    payload = await _save_payload(
        db,
        data,
        default_type=CreativeType.TEXT.value,
        user_id=user_id,
        offer_id=offer.id,
    )
    creative = await CreativeService(db).create(
        offer=offer,
        user_id=user_id,
        partner_id=None,
        creative_type=payload["type"],
        source=CreativeSource.AI.value if data.generation_id else CreativeSource.BUSINESS.value,
        status=CreativeStatus.DRAFT.value,
        title=payload["title"],
        text_content=payload["text_content"],
        asset_id=payload["asset_id"],
        language=payload["language"],
        channel=payload["channel"],
        image_format=payload["format"],
        generation_id=data.generation_id,
        selected_variant=payload["selected_variant"],
    )
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/{creative_id}/publish")
async def publish_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    creative = await service.publish(creative, offer=offer, user_id=parse_id(session_data["user_id"]))
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/{creative_id}/archive")
async def archive_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    creative = await service.archive(creative)
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/{creative_id}/unpublish")
async def unpublish_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    creative = await service.unpublish(creative)
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/{creative_id}/regenerate")
async def regenerate_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    creative = await regenerate_promo_material(
        db,
        offer=offer,
        creative=creative,
        user_id=parse_id(session_data["user_id"]),
    )
    return await _with_asset(db, offer_id, creative)


@router.delete("/{offer_id}/creatives/{creative_id}")
async def delete_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    await service.delete(creative)
    return {"ok": True}


@router.patch("/{offer_id}/creatives/{creative_id}")
async def update_creative(
    offer_id: str,
    creative_id: str,
    data: UpdateCreativeRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    service = CreativeService(db)
    creative = await service.get_for_business(offer, parse_id(creative_id))
    content = dict(creative.text_content or {})
    if data.headline is not None:
        content["headline"] = data.headline
    if data.body is not None:
        content["body"] = data.body
    if data.cta is not None:
        content["cta"] = data.cta
    if data.hashtags is not None:
        content["hashtags"] = data.hashtags
    creative = await service.update_content(
        creative,
        offer=offer,
        user_id=parse_id(session_data["user_id"]),
        title=data.title if data.title is not None else content.get("headline"),
        text_content=content,
    )
    return await _with_asset(db, offer_id, creative)


@router.post("/{offer_id}/creatives/{creative_id}/rewrite")
async def rewrite_offer_creative(
    offer_id: str,
    creative_id: str,
    data: RewriteCreativeRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    creative = await CreativeService(db).get_for_business(offer, parse_id(creative_id))
    return await rewrite_creative(
        db,
        offer=offer,
        creative=creative,
        user_id=parse_id(session_data["user_id"]),
        instruction=data.instruction,
    )


@router.get("/{offer_id}/creatives/{creative_id}/file")
async def download_creative_file(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    offer = await get_business_offer(db, offer_id, parse_id(session_data["active_business_id"]))
    creative = await CreativeService(db).get_for_business(offer, parse_id(creative_id))
    return await _file_response(db, creative)


@router.get("/{offer_id}/promo-materials/{creative_id}/image")
async def download_promo_material_image(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await download_creative_file(offer_id, creative_id, session_data, db)


async def _save_payload(
    db: AsyncSession,
    data: SaveCreativeRequest,
    *,
    default_type: str,
    user_id: int,
    offer_id: int,
) -> dict:
    variant = {}
    request_meta = {}
    if data.generation_id:
        generation = await AiGenerationService(db).get(data.generation_id)
        if (
            not generation
            or not generation.result
            or generation.user_id != user_id
            or generation.offer_id != offer_id
        ):
            raise AppError("AI_GENERATION_NOT_FOUND", "Generation not found", 404)
        variants = (generation.result or {}).get("variants") or []
        if data.variant_index < 0 or data.variant_index >= len(variants):
            raise AppError("CREATIVE_VARIANT_INVALID", "Variant not found", 400)
        variant = variants[data.variant_index]
        request_meta = generation.request or {}
        generation.selected_variant = variant.get("kind")
    creative_type = normalize_type(data.type or request_meta.get("type") or default_type)
    text_content = None
    asset_id = variant.get("asset_id")
    if creative_type != CreativeType.BANNER.value:
        text_content = {
            "headline": data.headline if data.headline is not None else variant.get("headline") or "",
            "body": data.body if data.body is not None else variant.get("body") or "",
            "cta": data.cta if data.cta is not None else variant.get("cta") or "",
            "hashtags": data.hashtags if data.hashtags is not None else variant.get("hashtags") or [],
        }
        if not data.generation_id and not (text_content["headline"] or text_content["body"]):
            raise AppError("CREATIVE_CONTENT_REQUIRED", "Creative text is required", 400)
    title = data.title or (text_content or {}).get("headline") or variant.get("headline")
    return {
        "type": creative_type,
        "title": title,
        "text_content": text_content,
        "asset_id": asset_id,
        "language": data.language or request_meta.get("language") or "ru",
        "channel": normalize_channel(data.channel or request_meta.get("channel")),
        "format": normalize_format(data.format or request_meta.get("format") or variant.get("format")),
        "selected_variant": variant.get("kind"),
    }


async def _with_asset(db: AsyncSession, offer_id: str, creative) -> dict:
    asset = None
    file_url = None
    if creative.asset_id:
        asset = (await db.execute(select(Asset).where(Asset.id == creative.asset_id))).scalar_one_or_none()
        file_url = f"/api/v1/business/offers/{offer_id}/creatives/{creative.id}/file"
    return serialize_creative(creative, asset=asset, file_url=file_url)


async def _file_response(db: AsyncSession, creative) -> Response:
    if not creative.asset_id:
        raise NotFoundError("Asset")
    asset = (await db.execute(select(Asset).where(Asset.id == creative.asset_id))).scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset")
    data = await AssetService(db).load(asset)
    content = creative.text_content or {}
    short_code = str(content.get("short_code") or "").strip()
    if is_qr_promo(creative) and short_code:
        data = compose_tracking_qr(data, short_code, content)
    return Response(
        content=data,
        media_type=asset.mime_type,
        headers={"Content-Disposition": f'inline; filename="creative-{creative.id}.png"'},
    )
