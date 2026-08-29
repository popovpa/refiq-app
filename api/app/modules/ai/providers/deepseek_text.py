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


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


class DeepSeekTextGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.DEEPSEEK_API_KEY
        self._model = model or settings.DEEPSEEK_PROMO_MODEL
        self._base_url = (base_url or settings.DEEPSEEK_BASE_URL).rstrip("/")
        self._timeout = (
            timeout_seconds if timeout_seconds is not None else settings.DEEPSEEK_TIMEOUT_SECONDS
        )
        self._max_retries = (
            max_retries if max_retries is not None else settings.DEEPSEEK_MAX_RETRIES
        )

    async def generate(self, request: TextGenerationRequest) -> GenerationResult:
        payload = {
            "model": self._model,
            "messages": _messages(request.system_prompt, request.user_prompt),
            "thinking": {"type": "disabled"},
        }
        return await self._complete(payload)

    async def generate_structured(self, request: StructuredGenerationRequest) -> GenerationResult:
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": _messages(
                _structured_system(request.system_prompt, request.schema),
                request.user_prompt,
            ),
            "response_format": {"type": "json_object"},
        }
        if request.reasoning_effort and request.reasoning_effort not in {"none", "off"}:
            payload["thinking"] = {"type": "enabled"}
            if request.reasoning_effort in {"low", "high", "max"}:
                payload["reasoning_effort"] = request.reasoning_effort
        else:
            payload["thinking"] = {"type": "disabled"}
        result = await self._complete(payload)
        if result.structured_data is None and result.content:
            try:
                parsed = json.loads(_strip_json_fence(result.content))
            except ValueError as exc:
                raise ai_invalid_response() from exc
            if not isinstance(parsed, dict):
                raise ai_invalid_response()
            return GenerationResult(
                generation_id=result.generation_id,
                provider=result.provider,
                model=result.model,
                structured_data=parsed,
                content=result.content,
                usage=result.usage,
                provider_metadata=result.provider_metadata,
                retry_count=result.retry_count,
            )
        return result

    async def _complete(self, payload: dict[str, Any]) -> GenerationResult:
        if not (self._api_key or "").strip():
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
                    operation="deepseek_chat",
                    model=str(payload.get("model") or self._model),
                    endpoint="/chat/completions",
                    status_code=response.status_code,
                    body=body,
                    extra={"retry": retries, "provider": "deepseek"},
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
        structured = None
        if isinstance(content, str) and content.strip():
            try:
                loaded = json.loads(_strip_json_fence(content))
                structured = loaded if isinstance(loaded, dict) else None
            except ValueError:
                structured = None

        usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        completion_details = (
            usage_raw.get("completion_tokens_details")
            if isinstance(usage_raw.get("completion_tokens_details"), dict)
            else {}
        )
        usage = ProviderUsage(
            input_tokens=_int(usage_raw.get("prompt_tokens")),
            output_tokens=_int(usage_raw.get("completion_tokens")),
            total_tokens=_int(usage_raw.get("total_tokens")),
            cached_input_tokens=_int(usage_raw.get("prompt_cache_hit_tokens")),
            reasoning_tokens=_int(completion_details.get("reasoning_tokens")),
            provider_request_id=body.get("id"),
            metadata=usage_raw,
        )
        return GenerationResult(
            generation_id=str(uuid.uuid4()),
            provider="deepseek",
            model=str(body.get("model") or self._model),
            structured_data=structured,
            content=content if isinstance(content, str) else None,
            usage=usage,
            provider_metadata={
                "id": body.get("id"),
                "finish_reason": ((body.get("choices") or [{}])[0] or {}).get("finish_reason"),
                "usage": usage_raw,
            },
            retry_count=retry_count,
        )


def _structured_system(system_prompt: str, schema: dict[str, Any]) -> str:
    return (
        f"{system_prompt}\n\n"
        "Return a single JSON object only. No markdown. No commentary.\n"
        f"The JSON must match this schema:\n{json.dumps(schema, ensure_ascii=False)}"
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
