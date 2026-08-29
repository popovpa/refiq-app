import base64

import httpx
import pytest

from app.modules.ai.generation import ImageGenerationRequest
from app.modules.ai.providers.fake import MIN_PNG
from app.modules.ai.providers.yandex_alice_art import (
    YandexAliceArtImageProvider,
    images_generations_url,
    yandex_image_size,
    yandex_model_uri,
)


TINY_PNG_B64 = base64.b64encode(MIN_PNG).decode()


def _request(**overrides) -> ImageGenerationRequest:
    payload = {
        "prompt": "EXEED RX для покупателя, только текст EXEED RX",
        "aspect_ratio": "1:1",
        "image_format": "square_1_1",
        "operation": "PROMO_IMAGE_GENERATE",
        "prompt_version": "promo-image-spec-v1",
    }
    payload.update(overrides)
    return ImageGenerationRequest(**payload)


def _client(monkeypatch, handler):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *args, **kwargs):
            return handler(url, kwargs.get("headers") or {}, kwargs.get("json") or {})

    monkeypatch.setattr("app.modules.ai.providers.yandex_alice_art.httpx.AsyncClient", FakeAsyncClient)


def test_yandex_endpoint_and_model_uri():
    assert images_generations_url("https://ai.api.cloud.yandex.net") == (
        "https://ai.api.cloud.yandex.net/v1/images/generations"
    )
    assert yandex_model_uri(folder_id="b1gfolder", model="aliceai-image-art-3.0") == (
        "art://b1gfolder/aliceai-image-art-3.0"
    )
    assert yandex_image_size("1:1") == "1024x1024"
    assert yandex_image_size("16:9") == "1536x1024"
    assert yandex_image_size("9:16") == "1024x1536"


@pytest.mark.asyncio
async def test_yandex_success_request(monkeypatch):
    captured: dict = {}

    def handler(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = payload
        return httpx.Response(
            200,
            json={"id": "img-1", "model": "aliceai-image-art-3.0", "data": [{"b64_json": TINY_PNG_B64}]},
        )

    _client(monkeypatch, handler)
    provider = YandexAliceArtImageProvider(
        api_key="yandex-key",
        folder_id="b1gfolder",
        model="aliceai-image-art-3.0",
        max_retries=0,
    )
    result = await provider.generate(_request())
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["headers"]["Authorization"] == "Api-Key yandex-key"
    assert captured["headers"]["x-folder-id"] == "b1gfolder"
    assert captured["json"]["model"] == "art://b1gfolder/aliceai-image-art-3.0"
    assert captured["json"]["prompt"] == _request().prompt
    assert captured["json"]["size"] == "1024x1024"
    assert captured["json"]["quality"] == "high"
    assert captured["json"]["output_format"] == "png"
    assert result.provider == "yandex"
    assert result.images[0].data == MIN_PNG
    assert result.images[0].mime_type == "image/png"


@pytest.mark.asyncio
async def test_yandex_rejects_oversized_prompt(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "YANDEX_AI_IMAGE_PROMPT_MAX_CHARS", 20)
    provider = YandexAliceArtImageProvider(api_key="k", folder_id="f", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(_request(prompt="x" * 50))
    assert exc.value.code == "AI_INVALID_REQUEST"


@pytest.mark.asyncio
async def test_yandex_malformed_response(monkeypatch):
    def handler(url, headers, payload):
        return httpx.Response(200, json={"data": []})

    _client(monkeypatch, handler)
    provider = YandexAliceArtImageProvider(api_key="k", folder_id="f", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(_request())
    assert exc.value.code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_yandex_timeout(monkeypatch):
    def handler(url, headers, payload):
        raise httpx.TimeoutException("timeout")

    _client(monkeypatch, handler)
    provider = YandexAliceArtImageProvider(api_key="k", folder_id="f", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(_request())
    assert exc.value.code == "AI_TIMEOUT"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(401, "AI_UNAUTHORIZED"), (403, "AI_UNAUTHORIZED"), (429, "AI_RATE_LIMIT"), (503, "AI_UNAVAILABLE")])
async def test_yandex_http_errors(monkeypatch, status, code):
    def handler(url, headers, payload):
        return httpx.Response(status, json={"code": status, "message": "denied"})

    _client(monkeypatch, handler)
    provider = YandexAliceArtImageProvider(api_key="k", folder_id="f", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(_request())
    assert exc.value.code == code
