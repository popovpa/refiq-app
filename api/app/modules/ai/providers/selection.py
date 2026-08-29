from app.core.config import settings


def text_provider_name() -> str:
    return (settings.AI_TEXT_PROVIDER or settings.AI_PROVIDER or "openai").strip().lower()


def image_provider_name() -> str:
    return (settings.AI_IMAGE_PROVIDER or settings.AI_PROVIDER or "openai").strip().lower()


def text_usage_model(model: str | None = None) -> str:
    name = text_provider_name()
    if model:
        return model
    if name == "deepseek":
        return (settings.DEEPSEEK_PROMO_MODEL or "deepseek-v4-pro").strip()
    if name == "openai":
        return (settings.OPENAI_MODEL or "").strip()
    return name


def image_usage_model() -> str:
    name = image_provider_name()
    if name == "yandex":
        return (settings.YANDEX_AI_IMAGE_MODEL or "aliceai-image-art-3.0").strip()
    if name == "openai":
        return (settings.OPENAI_IMAGE_MODEL or "").strip()
    return name


def promo_text_model(*, fast: bool = False) -> str:
    if text_provider_name() == "deepseek":
        if fast:
            return (settings.DEEPSEEK_FAST_MODEL or settings.DEEPSEEK_PROMO_MODEL or "deepseek-v4-flash").strip()
        return (settings.DEEPSEEK_PROMO_MODEL or "deepseek-v4-pro").strip()
    return (settings.OPENAI_PROMO_MODEL or settings.OPENAI_MODEL).strip()


def promo_reasoning(*, heavy: bool = True) -> str | None:
    if text_provider_name() == "deepseek":
        return "high" if heavy else None
    value = (settings.OPENAI_PROMO_REASONING_EFFORT or "").strip().lower()
    return value or None
