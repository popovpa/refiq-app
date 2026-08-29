from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.modules.ai.errors import (
    AiError,
    ai_invalid_response,
    ai_not_configured,
    ai_timeout,
    ai_unavailable,
    is_retryable_provider_error,
    log_provider_http_error,
    map_provider_http_error,
)
from app.modules.ai.generation import (
    GeneratedImage,
    GenerationResult,
    ImageGenerationRequest,
    ProviderUsage,
)

logger = structlog.get_logger()

# Semantic RefIQ formats stay in the application layer. Alice only gets a
# nearest supported pixel size.
_YANDEX_SIZES = {
    "1:1": "1024x1024",
    "4:5": "1024x1280",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
}
_SIZE_DIMENSIONS = {
    "1024x1024": (1024, 1024),
    "1024x1280": (1024, 1280),
    "1536x1024": (1536, 1024),
    "1024x1536": (1024, 1536),
}


def yandex_image_size(aspect_ratio: str) -> str:
    return _YANDEX_SIZES.get((aspect_ratio or "1:1").strip(), "1024x1024")


def yandex_model_uri(*, folder_id: str | None = None, model: str | None = None) -> str:
    folder = (folder_id if folder_id is not None else settings.YANDEX_AI_FOLDER_ID).strip()
    name = (model if model is not None else settings.YANDEX_AI_IMAGE_MODEL).strip()
    if name.startswith("art://"):
        return name
    return f"art://{folder}/{name or 'aliceai-image-art-3.0'}"


def images_generations_url(base_url: str | None = None) -> str:
    base = (base_url or settings.YANDEX_AI_BASE_URL).rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/images/generations"
    return f"{base}/v1/images/generations"


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _normalize_error_body(body: dict[str, Any]) -> dict[str, Any]:
    if isinstance(body.get("error"), dict):
        return body
    message = str(body.get("message") or body.get("error") or "").strip()
    code = str(body.get("code") or body.get("errorCode") or "").strip()
    if message or code:
        return {"error": {"code": code or None, "type": code or None, "message": message}}
    return body


class YandexAliceArtImageProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        folder_id: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.YANDEX_AI_API_KEY
        self._folder_id = folder_id if folder_id is not None else settings.YANDEX_AI_FOLDER_ID
        self._model = model or settings.YANDEX_AI_IMAGE_MODEL
        self._base_url = (base_url or settings.YANDEX_AI_BASE_URL).rstrip("/")
        self._timeout = (
            timeout_seconds if timeout_seconds is not None else settings.YANDEX_AI_IMAGE_TIMEOUT_SECONDS
        )
        self._max_retries = max_retries if max_retries is not None else settings.AI_MAX_RETRIES

    async def generate(self, request: ImageGenerationRequest) -> GenerationResult:
        if not (self._api_key or "").strip() or not (self._folder_id or "").strip():
            raise ai_not_configured()
        limit = int(settings.YANDEX_AI_IMAGE_PROMPT_MAX_CHARS or 500)
        if len(request.prompt or "") > limit:
            raise AiError("AI_INVALID_REQUEST", "Image prompt exceeds provider limit", 400)

        size = yandex_image_size(request.aspect_ratio)
        payload = {
            "model": yandex_model_uri(folder_id=self._folder_id, model=self._model),
            "prompt": request.prompt,
            "n": max(1, request.n),
            "size": size,
            "quality": "high",
            "output_format": "png",
        }
        return await self._complete(payload, size)

    async def _complete(self, payload: dict[str, Any], size: str) -> GenerationResult:
        retries = 0
        last_error = None
        url = images_generations_url(self._base_url)
        while retries <= self._max_retries:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        url,
                        headers={
                            "Authorization": f"Api-Key {self._api_key}",
                            "Content-Type": "application/json",
                            "x-folder-id": self._folder_id,
                        },
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                last_error = ai_timeout()
                last_error.retry_count = retries
                if retries >= self._max_retries:
                    raise last_error from exc
                retries += 1
                await asyncio.sleep(0.4 * retries)
                continue
            except httpx.HTTPError as exc:
                last_error = ai_unavailable()
                last_error.retry_count = retries
                if retries >= self._max_retries:
                    raise last_error from exc
                retries += 1
                await asyncio.sleep(0.4 * retries)
                continue

            if response.status_code >= 400:
                body = _normalize_error_body(_json_body(response))
                log_provider_http_error(
                    logger,
                    operation="yandex_alice_art",
                    model=str(payload.get("model") or self._model),
                    endpoint="/v1/images/generations",
                    status_code=response.status_code,
                    body=body,
                    extra={"retry": retries, "provider": "yandex", "prompt_chars": len(payload.get("prompt") or "")},
                )
                error = map_provider_http_error(response.status_code, body)
                error.retry_count = retries
                if is_retryable_provider_error(response.status_code, body) and retries < self._max_retries:
                    last_error = error
                    retries += 1
                    await asyncio.sleep(0.4 * retries)
                    continue
                raise error

            try:
                body = response.json()
            except ValueError as orig:
                raise ai_invalid_response() from orig
            if not isinstance(body, dict):
                raise ai_invalid_response()
            return self._to_result(body, size, retries)

        raise last_error or ai_unavailable()

    def _to_result(self, body: dict[str, Any], size: str, retry_count: int) -> GenerationResult:
        images = _decode_images(body)
        if not images:
            raise ai_invalid_response()
        width, height = _SIZE_DIMENSIONS.get(size, (None, None))
        generated = [
            GeneratedImage(
                data=item,
                mime_type="image/png",
                width=width,
                height=height,
            )
            for item in images
        ]
        usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="yandex",
            model=str(body.get("model") or self._model),
            structured_data=None,
            content=None,
            usage=ProviderUsage(
                input_tokens=_int(usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens")),
                output_tokens=_int(usage_raw.get("completion_tokens") or usage_raw.get("output_tokens")),
                total_tokens=_int(usage_raw.get("total_tokens")),
                provider_request_id=str(body.get("id") or body.get("created") or "") or None,
                metadata=usage_raw,
            ),
            provider_metadata={
                "id": body.get("id"),
                "size": size,
                "api": "images",
            },
            retry_count=retry_count,
            images=generated,
        )


def _decode_images(body: dict[str, Any]) -> list[bytes]:
    items = body.get("data") if isinstance(body.get("data"), list) else []
    if not items and isinstance(body.get("images"), list):
        items = body["images"]
    decoded: list[bytes] = []
    for item in items:
        raw = None
        if isinstance(item, dict):
            raw = item.get("b64_json") or item.get("image") or item.get("data")
        elif isinstance(item, str):
            raw = item
        if not raw:
            continue
        try:
            decoded.append(base64.b64decode(raw))
        except (ValueError, TypeError) as exc:
            raise ai_invalid_response() from exc
    return decoded


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
