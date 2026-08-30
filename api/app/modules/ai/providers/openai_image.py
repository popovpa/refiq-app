from __future__ import annotations

import asyncio
import base64
import time
import uuid
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.modules.ai.errors import (
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

# Business formats stay in the application layer. This adapter maps them to
# the closest size the configured OpenAI image model accepts.
_GPT_IMAGE_SIZES = {
    "1:1": "1024x1024",
    "4:5": "1024x1536",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
}
_DALLE_SIZES = {
    "1:1": "1024x1024",
    "4:5": "1024x1792",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
}
_SIZE_DIMENSIONS = {
    "1024x1024": (1024, 1024),
    "1024x1536": (1024, 1536),
    "1536x1024": (1536, 1024),
    "1024x1792": (1024, 1792),
    "1792x1024": (1792, 1024),
}


def uses_images_api(model: str) -> bool:
    name = (model or "").strip().lower()
    return name.startswith("dall-e") or name.startswith("gpt-image")


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


class OpenAIImageGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_IMAGE_MODEL
        self._base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self._timeout = (
            timeout_seconds if timeout_seconds is not None else settings.AI_IMAGE_TIMEOUT_SECONDS
        )
        self._max_retries = max_retries if max_retries is not None else settings.AI_MAX_RETRIES

    async def generate(self, request: ImageGenerationRequest) -> GenerationResult:
        if not self._api_key.strip():
            raise ai_not_configured()

        size = self._provider_size(request.aspect_ratio)
        native = uses_images_api(self._model)
        path = "/images/generations" if native else "/responses"
        endpoint = f"{self._base_url}{path}"
        payload = self._images_payload(request, size) if native else self._responses_payload(request, size)
        logger.info(
            "openai_image_request",
            model=self._model,
            endpoint=path,
            size=size,
            aspect_ratio=request.aspect_ratio,
            image_format=request.image_format,
            prompt_chars=len(request.prompt or ""),
            prompt=request.prompt,
            timeout_seconds=self._timeout,
            operation=request.operation,
        )

        retries = 0
        last_error = None
        while retries <= self._max_retries:
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                last_error = ai_timeout()
                last_error.retry_count = retries
                last_error.provider_metadata = {
                    "endpoint": path,
                    "model": self._model,
                    "size": size,
                    "timeout_seconds": self._timeout,
                }
                logger.warning(
                    "openai_image_timeout",
                    model=self._model,
                    endpoint=path,
                    size=size,
                    timeout_seconds=self._timeout,
                    retry=retries,
                    operation=request.operation,
                )
                if retries >= self._max_retries:
                    raise last_error from exc
                retries += 1
                await asyncio.sleep(0.4 * retries)
                continue
            except httpx.HTTPError as exc:
                last_error = ai_unavailable()
                last_error.retry_count = retries
                last_error.provider_metadata = {
                    "endpoint": path,
                    "model": self._model,
                    "http_error": type(exc).__name__,
                }
                logger.warning(
                    "openai_image_transport_error",
                    model=self._model,
                    endpoint=path,
                    error_type=type(exc).__name__,
                    retry=retries,
                    operation=request.operation,
                )
                if retries >= self._max_retries:
                    raise last_error from exc
                retries += 1
                await asyncio.sleep(0.4 * retries)
                continue

            elapsed_ms = int((time.monotonic() - started) * 1000)
            if response.status_code >= 400:
                body = _json_body(response)
                error = map_provider_http_error(response.status_code, body)
                error.retry_count = retries
                error.provider_metadata = {
                    **(error.provider_metadata or {}),
                    "endpoint": path,
                    "model": self._model,
                    "size": size,
                    "latency_ms": elapsed_ms,
                }
                log_provider_http_error(
                    logger,
                    operation=request.operation,
                    model=self._model,
                    endpoint=path,
                    status_code=response.status_code,
                    body=body,
                    extra={"size": size, "retry": retries, "latency_ms": elapsed_ms},
                )
                if is_retryable_provider_error(response.status_code, body) and retries < self._max_retries:
                    last_error = error
                    retries += 1
                    await asyncio.sleep(0.4 * retries)
                    continue
                raise error

            try:
                body = response.json()
            except ValueError as orig:
                logger.warning(
                    "openai_image_invalid_json",
                    model=self._model,
                    endpoint=path,
                    status_code=response.status_code,
                    body_chars=len(response.text or ""),
                    operation=request.operation,
                )
                raise ai_invalid_response() from orig
            if not isinstance(body, dict):
                raise ai_invalid_response()
            try:
                result = (
                    self._to_result(body, size, retries)
                    if native
                    else self._to_result_from_responses(body, size, retries)
                )
            except Exception:
                logger.warning(
                    "openai_image_parse_failed",
                    model=self._model,
                    endpoint=path,
                    size=size,
                    body_keys=sorted(body.keys()),
                    output_types=_output_types(body),
                    has_data=bool(body.get("data")),
                    operation=request.operation,
                )
                raise
            logger.info(
                "openai_image_success",
                model=result.model,
                endpoint=path,
                size=size,
                image_count=len(result.images),
                image_bytes=len(result.images[0].data) if result.images else 0,
                latency_ms=elapsed_ms,
                retry=retries,
                operation=request.operation,
            )
            return result

        raise last_error or ai_unavailable()

    def _images_payload(self, request: ImageGenerationRequest, size: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": request.prompt,
            "size": size,
            "n": max(1, min(request.n, 1)),
        }
        if self._model.startswith("dall-e"):
            payload["response_format"] = "b64_json"
        return payload

    def _responses_payload(self, request: ImageGenerationRequest, size: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "input": request.prompt,
            "tools": [{"type": "image_generation", "size": size}],
        }
        effort = (settings.OPENAI_PROMO_REASONING_EFFORT or "").strip()
        if effort:
            payload["reasoning"] = {"effort": effort}
        return payload

    def _provider_size(self, aspect_ratio: str) -> str:
        table = _DALLE_SIZES if self._model.startswith("dall-e") else _GPT_IMAGE_SIZES
        return table.get(aspect_ratio, table["1:1"])

    def _to_result(self, body: dict[str, Any], size: str, retry_count: int) -> GenerationResult:
        images: list[GeneratedImage] = []
        for item in body.get("data") or []:
            if not isinstance(item, dict):
                continue
            data = _decode_image(item.get("b64_json"))
            if data is None:
                raise ai_invalid_response()
            width, height = _SIZE_DIMENSIONS.get(size, (None, None))
            images.append(
                GeneratedImage(
                    data=data,
                    mime_type="image/png",
                    width=width,
                    height=height,
                    revised_prompt=item.get("revised_prompt"),
                )
            )
        if not images:
            raise ai_invalid_response()
        return self._build_result(body, images, size, retry_count, api="images")

    def _to_result_from_responses(self, body: dict[str, Any], size: str, retry_count: int) -> GenerationResult:
        images: list[GeneratedImage] = []
        failed_calls = 0
        for item in body.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "image_generation_call":
                continue
            if item.get("status") and item.get("status") != "completed":
                failed_calls += 1
                logger.warning(
                    "openai_image_tool_failed",
                    model=self._model,
                    status=item.get("status"),
                    tool_error=str(item.get("error") or "")[:300],
                )
                continue
            data = _decode_image(item.get("result"))
            if data is None:
                continue
            width, height = _SIZE_DIMENSIONS.get(size, (None, None))
            images.append(
                GeneratedImage(
                    data=data,
                    mime_type="image/png",
                    width=width,
                    height=height,
                    revised_prompt=item.get("revised_prompt"),
                )
            )
        if not images:
            error = ai_invalid_response()
            error.provider_metadata = {
                "endpoint": "/responses",
                "model": self._model,
                "output_types": _output_types(body),
                "failed_image_calls": failed_calls,
            }
            raise error
        return self._build_result(body, images, size, retry_count, api="responses")

    def _build_result(
        self,
        body: dict[str, Any],
        images: list[GeneratedImage],
        size: str,
        retry_count: int,
        *,
        api: str,
    ) -> GenerationResult:
        usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        usage = ProviderUsage(
            input_tokens=_int(
                usage_raw.get("input_tokens") or usage_raw.get("prompt_tokens")
            ),
            output_tokens=_int(
                usage_raw.get("output_tokens") or usage_raw.get("completion_tokens")
            ),
            total_tokens=_int(usage_raw.get("total_tokens")),
            provider_request_id=_as_request_id(body),
            metadata=usage_raw,
        )
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="openai",
            model=str(body.get("model") or self._model),
            structured_data=None,
            content=None,
            usage=usage,
            provider_metadata={
                "id": body.get("id"),
                "created": body.get("created"),
                "size": size,
                "image_count": len(images),
                "api": api,
            },
            retry_count=retry_count,
            images=images,
        )


def _as_request_id(body: dict[str, Any]) -> str | None:
    value = body.get("id")
    if value is None:
        value = body.get("created")
    if value is None:
        return None
    return str(value)[:120]


def _decode_image(encoded: Any) -> bytes | None:
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    value = encoded.strip()
    if "," in value and value.lower().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value)
    except (TypeError, ValueError):
        return None


def _output_types(body: dict[str, Any]) -> list[str]:
    types: list[str] = []
    for item in body.get("output") or []:
        if isinstance(item, dict) and item.get("type"):
            types.append(str(item["type"]))
    return types


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
