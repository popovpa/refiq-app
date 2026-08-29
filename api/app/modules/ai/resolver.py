from app.modules.ai.capabilities import (
    IMAGE_CAPABILITIES,
    TEXT_CAPABILITIES,
    UNIMPLEMENTED_CAPABILITIES,
    Capability,
)
from app.modules.ai.errors import ai_capability_unavailable, ai_not_configured
from app.modules.ai.providers.base import ImageGenerationProvider, TextGenerationProvider
from app.modules.ai.providers.deepseek_text import DeepSeekTextGenerationProvider
from app.modules.ai.providers.fake import FakeImageGenerationProvider, FakeTextGenerationProvider
from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider
from app.modules.ai.providers.openai_text import OpenAITextGenerationProvider
from app.modules.ai.providers.selection import image_provider_name, text_provider_name
from app.modules.ai.providers.yandex_alice_art import YandexAliceArtImageProvider

_fake_text = FakeTextGenerationProvider()
_fake_image = FakeImageGenerationProvider()


def get_fake_provider() -> FakeTextGenerationProvider:
    return _fake_text


def get_fake_image_provider() -> FakeImageGenerationProvider:
    return _fake_image


class ProviderResolver:
    def text(self, capability: Capability) -> TextGenerationProvider:
        if capability in UNIMPLEMENTED_CAPABILITIES:
            raise ai_capability_unavailable()
        if capability not in TEXT_CAPABILITIES:
            raise ai_capability_unavailable()
        name = text_provider_name()
        if name == "fake":
            return get_fake_provider()
        if name == "openai":
            return OpenAITextGenerationProvider()
        if name == "deepseek":
            return DeepSeekTextGenerationProvider()
        raise ai_not_configured()

    def image(self, capability: Capability) -> ImageGenerationProvider:
        if capability in UNIMPLEMENTED_CAPABILITIES:
            raise ai_capability_unavailable()
        if capability not in IMAGE_CAPABILITIES:
            raise ai_capability_unavailable()
        name = image_provider_name()
        if name == "fake":
            return get_fake_image_provider()
        if name == "openai":
            return OpenAIImageGenerationProvider()
        if name == "yandex":
            return YandexAliceArtImageProvider()
        raise ai_not_configured()


def get_provider_resolver() -> ProviderResolver:
    return ProviderResolver()
