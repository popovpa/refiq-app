from app.common.enums import BannerFormat, CreativeChannel, CreativeType
from app.core.exceptions import AppError

TYPE_ALIASES = {
    "text": CreativeType.TEXT.value,
    "TEXT": CreativeType.TEXT.value,
    "social_post": CreativeType.SOCIAL_POST.value,
    "SOCIAL_POST": CreativeType.SOCIAL_POST.value,
    "banner": CreativeType.BANNER.value,
    "BANNER": CreativeType.BANNER.value,
    "image": CreativeType.BANNER.value,
    "IMAGE": CreativeType.BANNER.value,
}

FORMAT_ALIASES = {
    "square_1_1": BannerFormat.SQUARE_1_1.value,
    "SQUARE_1_1": BannerFormat.SQUARE_1_1.value,
    "portrait_4_5": BannerFormat.PORTRAIT_4_5.value,
    "PORTRAIT_4_5": BannerFormat.PORTRAIT_4_5.value,
    "landscape_16_9": BannerFormat.LANDSCAPE_16_9.value,
    "LANDSCAPE_16_9": BannerFormat.LANDSCAPE_16_9.value,
    "story_9_16": BannerFormat.STORY_9_16.value,
    "STORY_9_16": BannerFormat.STORY_9_16.value,
}

CHANNEL_ALIASES = {
    "general": CreativeChannel.GENERAL.value,
    "GENERAL": CreativeChannel.GENERAL.value,
    "telegram": CreativeChannel.TELEGRAM.value,
    "TELEGRAM": CreativeChannel.TELEGRAM.value,
    "social": CreativeChannel.SOCIAL.value,
    "SOCIAL": CreativeChannel.SOCIAL.value,
    "vk": CreativeChannel.VK.value,
    "VK": CreativeChannel.VK.value,
    "instagram": CreativeChannel.INSTAGRAM.value,
    "INSTAGRAM": CreativeChannel.INSTAGRAM.value,
    "yandex_direct": CreativeChannel.YANDEX_DIRECT.value,
    "YANDEX_DIRECT": CreativeChannel.YANDEX_DIRECT.value,
    "meta_ads": CreativeChannel.META_ADS.value,
    "META_ADS": CreativeChannel.META_ADS.value,
    "facebook": CreativeChannel.META_ADS.value,
    "google_ads": CreativeChannel.GOOGLE_ADS.value,
    "GOOGLE_ADS": CreativeChannel.GOOGLE_ADS.value,
    "tiktok_ads": CreativeChannel.TIKTOK_ADS.value,
    "TIKTOK_ADS": CreativeChannel.TIKTOK_ADS.value,
    "vk_ads": CreativeChannel.VK.value,
    "VK_ADS": CreativeChannel.VK.value,
    "other": CreativeChannel.OTHER.value,
    "OTHER": CreativeChannel.OTHER.value,
}

BANNER_ASPECT = {
    BannerFormat.SQUARE_1_1.value: "1:1",
    BannerFormat.PORTRAIT_4_5.value: "4:5",
    BannerFormat.LANDSCAPE_16_9.value: "16:9",
    BannerFormat.STORY_9_16.value: "9:16",
}

MVP_TYPES = {CreativeType.TEXT.value, CreativeType.SOCIAL_POST.value, CreativeType.BANNER.value}
MAX_TEXT_VARIANTS = 3
MAX_IMAGE_VARIANTS = 1


def normalize_type(value: str | None) -> str:
    if not value:
        raise AppError("CREATIVE_TYPE_INVALID", "Unsupported creative type", 400)
    mapped = TYPE_ALIASES.get(value) or TYPE_ALIASES.get(value.lower())
    if mapped not in MVP_TYPES:
        raise AppError("CREATIVE_TYPE_INVALID", "Unsupported creative type", 400)
    return mapped


def normalize_format(value: str | None) -> str | None:
    if not value:
        return None
    mapped = FORMAT_ALIASES.get(value) or FORMAT_ALIASES.get(value.lower())
    if not mapped:
        raise AppError("CREATIVE_FORMAT_INVALID", "Unsupported banner format", 400)
    return mapped


def normalize_channel(value: str | None) -> str | None:
    if not value:
        return None
    mapped = CHANNEL_ALIASES.get(value) or CHANNEL_ALIASES.get(value.lower())
    return mapped or CreativeChannel.OTHER.value


def clamp_variants(creative_type: str, variants: int | None) -> int:
    maximum = MAX_IMAGE_VARIANTS if creative_type == CreativeType.BANNER.value else MAX_TEXT_VARIANTS
    default = maximum
    count = default if variants is None else int(variants)
    return max(1, min(count, maximum))
