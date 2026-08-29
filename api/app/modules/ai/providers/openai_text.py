from __future__ import annotations

import asyncio
import json
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
    GenerationResult,
    ProviderUsage,
    StructuredGenerationRequest,
    TextGenerationRequest,
)

logger = structlog.get_logger()


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


class OpenAITextGenerationProvider:
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
        self._model = model or settings.OPENAI_MODEL
        self._base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds if timeout_seconds is not None else settings.AI_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else settings.AI_MAX_RETRIES

    async def generate(self, request: TextGenerationRequest) -> GenerationResult:
        payload = {
            "model": self._model,
            "messages": _messages(request.system_prompt, request.user_prompt),
        }
        return await self._complete(payload)

    async def generate_structured(self, request: StructuredGenerationRequest) -> GenerationResult:
        payload = {
            "model": request.model or self._model,
            "messages": _messages(request.system_prompt, request.user_prompt),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }
        if request.reasoning_effort:
            payload["reasoning_effort"] = request.reasoning_effort
        result = await self._complete(payload)
        if result.structured_data is None and result.content:
            try:
                parsed = json.loads(result.content)
            except ValueError as exc:
                raise ai_invalid_response() from exc
            return GenerationResult(
                generation_id=result.generation_id,
                provider=result.provider,
                model=result.model,
                structured_data=parsed if isinstance(parsed, dict) else None,
                content=result.content,
                usage=result.usage,
                provider_metadata=result.provider_metadata,
                retry_count=result.retry_count,
            )
        return result

    async def _complete(self, payload: dict[str, Any]) -> GenerationResult:
        if not self._api_key.strip():
            raise ai_not_configured()

        retries = 0
        last_error = None
        while retries <= self._max_retries:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
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
                body = _json_body(response)
                log_provider_http_error(
                    logger,
                    operation=str(payload.get("response_format", {}).get("json_schema", {}).get("name") or "text"),
                    model=str(payload.get("model") or self._model),
                    endpoint="/chat/completions",
                    status_code=response.status_code,
                    body=body,
                    extra={"retry": retries},
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
            if not isinstance(body, dict) or not (body.get("choices") or []):
                raise ai_invalid_response()
            return self._to_result(body, retries)

        raise last_error or ai_unavailable()

    def _to_result(self, body: dict[str, Any], retry_count: int) -> GenerationResult:
        choices = body.get("choices") or []
        message = (choices[0].get("message") if choices else {}) or {}
        content = message.get("content")
        parsed = message.get("parsed")
        structured = parsed if isinstance(parsed, dict) else None
        if structured is None and isinstance(content, str) and content.strip().startswith("{"):
            try:
                loaded = json.loads(content)
                structured = loaded if isinstance(loaded, dict) else None
            except ValueError:
                structured = None

        usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        prompt_details = usage_raw.get("prompt_tokens_details") if isinstance(usage_raw.get("prompt_tokens_details"), dict) else {}
        completion_details = (
            usage_raw.get("completion_tokens_details")
            if isinstance(usage_raw.get("completion_tokens_details"), dict)
            else {}
        )
        usage = ProviderUsage(
            input_tokens=_int(usage_raw.get("prompt_tokens")),
            output_tokens=_int(usage_raw.get("completion_tokens")),
            total_tokens=_int(usage_raw.get("total_tokens")),
            cached_input_tokens=_int(prompt_details.get("cached_tokens")),
            reasoning_tokens=_int(completion_details.get("reasoning_tokens")),
            provider_request_id=body.get("id"),
            metadata=usage_raw,
        )
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="openai",
            model=str(body.get("model") or self._model),
            structured_data=structured,
            content=content if isinstance(content, str) else None,
            usage=usage,
            provider_metadata=_safe_metadata(body),
            retry_count=retry_count,
        )


def _messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_metadata(body: dict[str, Any]) -> dict[str, Any]:
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    return {
        "id": body.get("id"),
        "object": body.get("object"),
        "created": body.get("created"),
        "system_fingerprint": body.get("system_fingerprint"),
        "service_tier": body.get("service_tier"),
        "usage": usage,
        "finish_reason": ((body.get("choices") or [{}])[0] or {}).get("finish_reason"),
    }
