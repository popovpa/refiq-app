from typing import Any

from app.core.exceptions import AppError

_MESSAGE_LIMIT = 500


class AiError(AppError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        retry_count: int = 0,
        provider_metadata: dict[str, Any] | None = None,
    ):
        super().__init__(code, message, status_code)
        self.retry_count = retry_count
        self.provider_metadata = provider_metadata or {}


def ai_not_configured() -> AiError:
    return AiError("AI_NOT_CONFIGURED", "AI is not configured", 503)


def ai_unavailable() -> AiError:
    return AiError("AI_UNAVAILABLE", "AI provider is temporarily unavailable", 503)


def ai_timeout() -> AiError:
    return AiError("AI_TIMEOUT", "AI request timed out", 504)


def ai_rate_limited() -> AiError:
    return AiError("AI_RATE_LIMIT", "AI provider rate limit exceeded", 429)


def ai_quota_exceeded() -> AiError:
    return AiError("AI_QUOTA_EXCEEDED", "AI provider quota exceeded", 503)


def ai_model_unavailable() -> AiError:
    return AiError("AI_MODEL_UNAVAILABLE", "Configured AI model is not available", 502)


def ai_invalid_response() -> AiError:
    return AiError("AI_INVALID_RESPONSE", "AI returned an invalid response", 502)


def ai_capability_unavailable() -> AiError:
    return AiError("AI_CAPABILITY_UNAVAILABLE", "This AI capability is not available", 501)


def provider_error_details(body: dict[str, Any] | None = None) -> dict[str, Any]:
    error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    message = str(error.get("message") or "").strip()
    if len(message) > _MESSAGE_LIMIT:
        message = message[:_MESSAGE_LIMIT]
    return {
        "provider_error_code": str(error.get("code") or "") or None,
        "provider_error_type": str(error.get("type") or "") or None,
        "provider_error_message": message or None,
        "provider_error_param": str(error.get("param") or "") or None,
    }


def log_provider_http_error(
    logger: Any,
    *,
    operation: str,
    model: str,
    endpoint: str,
    status_code: int,
    body: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    logger.warning(
        "openai_http_error",
        operation=operation,
        model=model,
        endpoint=endpoint,
        status_code=status_code,
        **provider_error_details(body),
        **(extra or {}),
    )


def map_provider_http_error(status_code: int, body: dict[str, Any] | None = None) -> AiError:
    error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    provider_code = str(error.get("code") or "")
    provider_type = str(error.get("type") or "")
    message = str(error.get("message") or "")
    fingerprint = f"{provider_code} {provider_type} {message}".lower()
    metadata = {"http_status": status_code, **provider_error_details(body)}

    if status_code in {401, 403}:
        return _with_meta(AiError("AI_UNAUTHORIZED", "AI provider rejected the request", 502), metadata)
    if "insufficient_quota" in fingerprint:
        return _with_meta(ai_quota_exceeded(), metadata)
    if _looks_like_model_error(status_code, fingerprint):
        return _with_meta(ai_model_unavailable(), metadata)
    if status_code == 429:
        return _with_meta(ai_rate_limited(), metadata)
    if status_code >= 500:
        return _with_meta(ai_unavailable(), metadata)
    return _with_meta(ai_unavailable(), metadata)


def is_retryable_provider_error(status_code: int, body: dict[str, Any] | None = None) -> bool:
    error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    fingerprint = f"{error.get('code') or ''} {error.get('type') or ''}".lower()
    if "insufficient_quota" in fingerprint or "model_not_found" in fingerprint:
        return False
    return status_code in {429, 500, 502, 503, 504}


def _looks_like_model_error(status_code: int, fingerprint: str) -> bool:
    if "model_not_found" in fingerprint:
        return True
    if status_code not in {400, 404}:
        return False
    return "model" in fingerprint and (
        "not found" in fingerprint
        or "does not exist" in fingerprint
        or "not support" in fingerprint
        or "invalid model" in fingerprint
        or "unknown model" in fingerprint
    )


def _with_meta(error: AiError, metadata: dict[str, Any]) -> AiError:
    error.provider_metadata = metadata
    return error
