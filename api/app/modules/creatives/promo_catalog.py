from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import BannerFormat, CreativeChannel, CreativeType
from app.core.exceptions import AppError
from app.modules.links.models import TrackingLink, TrackingLinkStatus

DEFAULT_QR_LAYOUT = {
    "qr_position": "bottom_right",
    "qr_safe_area": {"x": 0.74, "y": 0.74, "w": 0.22, "h": 0.22},
    "layout_variant": "bottom_right_quiet",
}

QR_SLOT_ID = "images_qr"


@dataclass(frozen=True)
class PromoSlot:
    id: str
    group: str
    label: str
    recommended: bool
    kind: str
    channel: str
    creative_type: str
    title: str
    image_format: str | None = None
    aspect_ratio: str | None = None
    image_count: int = 1
    in_catalog: bool = True


def _text(
    slot_id: str,
    *,
    label: str,
    kind: str,
    channel: str,
    creative_type: str,
    title: str | None = None,
    recommended: bool = True,
    in_catalog: bool = True,
) -> PromoSlot:
    return PromoSlot(
        id=slot_id,
        group="text",
        label=label,
        recommended=recommended,
        kind=kind,
        channel=channel,
        creative_type=creative_type,
        title=title or label,
        in_catalog=in_catalog,
    )


SLOTS: dict[str, PromoSlot] = {
    "telegram": _text(
        "telegram",
        label="Telegram",
        kind="social",
        channel=CreativeChannel.TELEGRAM.value,
        creative_type=CreativeType.SOCIAL_POST.value,
    ),
    "meta_ads": _text(
        "meta_ads",
        label="Meta Ads (Facebook)",
        kind="meta",
        channel=CreativeChannel.META_ADS.value,
        creative_type=CreativeType.TEXT.value,
    ),
    "google_ads": _text(
        "google_ads",
        label="Google Ads",
        kind="search_ads",
        channel=CreativeChannel.GOOGLE_ADS.value,
        creative_type=CreativeType.TEXT.value,
    ),
    "yandex_direct": _text(
        "yandex_direct",
        label="Яндекс Директ",
        kind="yandex",
        channel=CreativeChannel.YANDEX_DIRECT.value,
        creative_type=CreativeType.TEXT.value,
    ),
    "vk_ads": _text(
        "vk_ads",
        label="VK Реклама",
        kind="social",
        channel=CreativeChannel.VK.value,
        creative_type=CreativeType.SOCIAL_POST.value,
    ),
    "tiktok_ads": _text(
        "tiktok_ads",
        label="TikTok Ads",
        kind="tiktok",
        channel=CreativeChannel.TIKTOK_ADS.value,
        creative_type=CreativeType.TEXT.value,
    ),
    "images_1_1": PromoSlot(
        id="images_1_1",
        group="image",
        label="Изображение 1:1",
        recommended=True,
        kind="image",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.BANNER.value,
        title="Изображение 1:1",
        image_format=BannerFormat.SQUARE_1_1.value,
        aspect_ratio="1:1",
        image_count=1,
    ),
    "images_16_9": PromoSlot(
        id="images_16_9",
        group="image",
        label="Изображение 16:9",
        recommended=False,
        kind="image",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.BANNER.value,
        title="Изображение 16:9",
        image_format=BannerFormat.LANDSCAPE_16_9.value,
        aspect_ratio="16:9",
        image_count=1,
    ),
    "images_9_16": PromoSlot(
        id="images_9_16",
        group="image",
        label="Изображение 9:16",
        recommended=False,
        kind="image",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.BANNER.value,
        title="Изображение 9:16",
        image_format=BannerFormat.STORY_9_16.value,
        aspect_ratio="9:16",
        image_count=1,
    ),
    QR_SLOT_ID: PromoSlot(
        id=QR_SLOT_ID,
        group="image",
        label="Изображение с QR-кодом",
        recommended=False,
        kind="qr_image",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.BANNER.value,
        title="Изображение с QR-кодом",
        image_format=BannerFormat.SQUARE_1_1.value,
        aspect_ratio="1:1",
        image_count=1,
    ),
    # Historical slots kept for regenerate / old GenerationItems. Hidden from catalog.
    "universal_ad": _text(
        "universal_ad",
        label="Универсальный рекламный текст",
        kind="copy",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.TEXT.value,
        recommended=False,
        in_catalog=False,
    ),
    "short_ad": _text(
        "short_ad",
        label="Короткий рекламный текст",
        kind="copy",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.TEXT.value,
        recommended=False,
        in_catalog=False,
    ),
    "headlines": _text(
        "headlines",
        label="5 заголовков",
        kind="headlines",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.TEXT.value,
        recommended=False,
        in_catalog=False,
    ),
    "descriptions": _text(
        "descriptions",
        label="3 коротких описания",
        kind="descriptions",
        channel=CreativeChannel.GENERAL.value,
        creative_type=CreativeType.TEXT.value,
        recommended=False,
        in_catalog=False,
    ),
    "telegram_posts": _text(
        "telegram_posts",
        label="Telegram",
        kind="social",
        channel=CreativeChannel.TELEGRAM.value,
        creative_type=CreativeType.SOCIAL_POST.value,
        recommended=False,
        in_catalog=False,
    ),
    "vk_posts": _text(
        "vk_posts",
        label="VK Реклама",
        kind="social",
        channel=CreativeChannel.VK.value,
        creative_type=CreativeType.SOCIAL_POST.value,
        recommended=False,
        in_catalog=False,
    ),
}

SLOT_ORDER = [slot_id for slot_id, slot in SLOTS.items() if slot.in_catalog]
RECOMMENDED_SLOT_IDS = [slot.id for slot in SLOTS.values() if slot.recommended and slot.in_catalog]


def resolve_slots(slot_ids: list[str] | None) -> list[PromoSlot]:
    selected = RECOMMENDED_SLOT_IDS if slot_ids is None else slot_ids
    seen: set[str] = set()
    resolved: list[PromoSlot] = []
    for slot_id in selected:
        if slot_id in seen:
            continue
        slot = SLOTS.get(slot_id)
        if slot is None:
            raise AppError("PROMO_SLOT_INVALID", f"Unknown promo slot: {slot_id}", 400)
        seen.add(slot_id)
        resolved.append(slot)
    if not resolved:
        raise AppError("PROMO_SLOTS_REQUIRED", "Select at least one material", 400)
    return resolved


def catalog_payload() -> dict:
    items = [slot for slot_id in SLOT_ORDER if (slot := SLOTS[slot_id]).in_catalog]
    return {
        "items": [
            {
                "id": slot.id,
                "group": slot.group,
                "label": slot.label,
                "recommended": slot.recommended,
            }
            for slot in items
        ],
        "recommended": RECOMMENDED_SLOT_IDS,
    }


def is_qr_promo(creative) -> bool:
    if getattr(creative, "selected_variant", None) == QR_SLOT_ID:
        return True
    content = getattr(creative, "text_content", None) or {}
    return bool(content.get("qr_safe_area") or content.get("qr_position"))


async def require_qr_tracking_link(
    db: AsyncSession,
    *,
    offer_id: int,
    tracking_link_id: int | None,
) -> TrackingLink:
    if tracking_link_id is None:
        raise AppError("PROMO_QR_LINK_REQUIRED", "Select a tracking link for the QR image", 400)
    link = (
        await db.execute(
            select(TrackingLink).where(
                TrackingLink.id == tracking_link_id,
                TrackingLink.offer_id == offer_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise AppError("PROMO_QR_LINK_INVALID", "Tracking link is not available for this offer", 400)
    if link.status != TrackingLinkStatus.ACTIVE.value:
        raise AppError("PROMO_QR_LINK_INVALID", "Tracking link is not active", 400)
    return link
