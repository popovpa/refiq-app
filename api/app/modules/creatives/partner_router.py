from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CreativeSource, CreativeStatus, CreativeType, LinkStatus
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.core.ids import parse_id
from app.core.permissions import require_partner_role
from app.modules.ai.application.creative.generate import (
    generate_creative,
    rewrite_creative,
)
from app.modules.ai.jobs import get_job_runner
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.creatives.access import get_partner_offer, get_partner_profile
from app.modules.creatives.business_router import (
    GenerateCreativeRequest,
    SaveCreativeRequest,
    UpdateCreativeRequest,
    RewriteCreativeRequest,
    _save_payload,
)
from app.modules.creatives.promo_catalog import is_qr_promo
from app.modules.creatives.qr_compose import compose_tracking_qr
from app.modules.creatives.serialize import serialize_creative
from app.modules.creatives.service import CreativeService
from app.modules.links.models import TrackingLink

router = APIRouter()


@router.get("/offers/{offer_id}/creatives")
async def list_partner_creatives(
    offer_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id)
    items = await CreativeService(db).list_for_partner(offer, profile.id)
    return {"items": [await _with_asset(db, offer_id, item) for item in items]}


@router.get("/offers/{offer_id}/creatives/{creative_id}")
async def get_partner_creative(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id)
    creative = await CreativeService(db).get_for_partner(offer, parse_id(creative_id), profile.id)
    return await _with_asset(db, offer_id, creative)


@router.post("/offers/{offer_id}/creatives/generate")
async def generate_partner_creative(
    offer_id: str,
    data: GenerateCreativeRequest,
    background_tasks: BackgroundTasks,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.creatives.normalize import normalize_channel, normalize_format, normalize_type

    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id, require_approved=True)
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


@router.post("/offers/{offer_id}/creatives")
async def create_partner_creative(
    offer_id: str,
    data: SaveCreativeRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id, require_approved=True)
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
        partner_id=profile.id,
        creative_type=payload["type"],
        source=CreativeSource.AI.value if data.generation_id else CreativeSource.PARTNER.value,
        status=CreativeStatus.ACTIVE.value,
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


@router.patch("/offers/{offer_id}/creatives/{creative_id}")
async def update_partner_creative(
    offer_id: str,
    creative_id: str,
    data: UpdateCreativeRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id, require_approved=True)
    service = CreativeService(db)
    creative = await service.get_for_partner(offer, parse_id(creative_id), profile.id)
    if creative.partner_id != profile.id:
        raise AppError("FORBIDDEN", "Cannot edit business creatives", 403)
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


@router.post("/offers/{offer_id}/creatives/{creative_id}/rewrite")
async def rewrite_partner_creative(
    offer_id: str,
    creative_id: str,
    data: RewriteCreativeRequest,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id, require_approved=True)
    creative = await CreativeService(db).get_for_partner(offer, parse_id(creative_id), profile.id)
    if creative.partner_id != profile.id:
        raise AppError("FORBIDDEN", "Cannot edit business creatives", 403)
    return await rewrite_creative(
        db,
        offer=offer,
        creative=creative,
        user_id=parse_id(session_data["user_id"]),
        instruction=data.instruction,
    )


@router.get("/offers/{offer_id}/creatives/{creative_id}/file")
async def download_partner_creative_file(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_partner_profile(db, session_data["user_id"])
    offer, _access = await get_partner_offer(db, offer_id, profile.id)
    creative = await CreativeService(db).get_for_partner(offer, parse_id(creative_id), profile.id)
    if not creative.asset_id:
        raise NotFoundError("Asset")
    asset = (await db.execute(select(Asset).where(Asset.id == creative.asset_id))).scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset")
    data = await AssetService(db).load(asset)
    if is_qr_promo(creative):
        short_code = await _partner_short_code(db, offer.id, profile.id)
        if short_code:
            data = compose_tracking_qr(data, short_code, creative.text_content or {})
    return Response(
        content=data,
        media_type=asset.mime_type,
        headers={"Content-Disposition": f'inline; filename="creative-{creative.id}.png"'},
    )


@router.get("/offers/{offer_id}/promo-materials/{creative_id}/image")
async def download_partner_promo_material_image(
    offer_id: str,
    creative_id: str,
    session_data: dict = Depends(require_partner_role),
    db: AsyncSession = Depends(get_db),
):
    return await download_partner_creative_file(offer_id, creative_id, session_data, db)


async def _with_asset(db: AsyncSession, offer_id: str, creative) -> dict:
    asset = None
    file_url = None
    if creative.asset_id:
        asset = (await db.execute(select(Asset).where(Asset.id == creative.asset_id))).scalar_one_or_none()
        file_url = f"/api/v1/partner/offers/{offer_id}/creatives/{creative.id}/file"
    return serialize_creative(creative, asset=asset, file_url=file_url)


async def _partner_short_code(db: AsyncSession, offer_id: int, partner_id: int) -> str | None:
    result = await db.execute(
        select(TrackingLink.short_code)
        .where(
            TrackingLink.offer_id == offer_id,
            TrackingLink.partner_id == partner_id,
            TrackingLink.status == LinkStatus.ACTIVE.value,
        )
        .order_by(TrackingLink.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
