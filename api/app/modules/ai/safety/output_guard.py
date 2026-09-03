from __future__ import annotations

import re
from typing import Any

from app.modules.ai.errors import AiError
from app.modules.ai.safety.events import SecurityEvent, log_security_event
from app.modules.ai.safety.grounding import guard_output_grounding
from app.modules.ai.safety.local_guard import inspect_local
from app.modules.ai.safety.operations import AiOperation, InputSource, allowed_fields_for
from app.modules.ai.safety.policy import AiOperationPolicy, get_operation_policy
from app.modules.ai.safety.verified_context import VerifiedContext

_LEAK = (
    "here is your system prompt",
    "here is the system prompt",
    "системный промпт",
    "developer instructions",
    "developer message",
    "openai_api_key",
    "begin system prompt",
)
_CODE_FENCE = re.compile(r"```(?:python|javascript|bash|sh|sql)\b", re.I)
_MAX_FIELD = {
    "name": 255,
    "description": 2000,
    "partner_notes": 4000,
    "value": 4000,
    "headline": 280,
    "body": 4000,
    "cta": 120,
    "imagePrompt": 4000,
}


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(flatten_text(item) for item in value)
    return str(value)


def guard_output(
    payload: Any,
    *,
    operation: AiOperation,
    user_id: int | None = None,
    offer_id: str | int | None = None,
    verified_context: VerifiedContext | None = None,
    policy: AiOperationPolicy | None = None,
    source_text: str | None = None,
) -> None:
    text = flatten_text(payload)
    lowered = text.casefold()
    if any(token in lowered for token in _LEAK):
        _reject(operation, user_id, offer_id, text, "SYSTEM_PROMPT_LEAK")
    local = inspect_local(text)
    if local.blocked and local.category in {"SYSTEM_PROMPT_EXTRACTION", "SECRET_EXTRACTION", "ROLE_OVERRIDE"}:
        _reject(operation, user_id, offer_id, text, local.category or "OUTPUT_INJECTION")
    if _CODE_FENCE.search(text) and operation != AiOperation.GENERATE_OFFER:
        _reject(operation, user_id, offer_id, text, "UNRELATED_TASK")
    _check_lengths(payload)
    allowed = allowed_fields_for(operation)
    if allowed and isinstance(payload, dict):
        unexpected = set(payload) - allowed - _always_allowed(operation)
        if unexpected and operation in {
            AiOperation.IMPROVE_OFFER_TITLE,
            AiOperation.IMPROVE_OFFER_DESCRIPTION,
            AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
        }:
            extra = unexpected - {"value"}
            if extra:
                _reject(operation, user_id, offer_id, text, "UNEXPECTED_FIELD")
    if operation in {
        AiOperation.IMPROVE_OFFER_TITLE,
        AiOperation.IMPROVE_OFFER_DESCRIPTION,
        AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
        AiOperation.REWRITE_CREATIVE,
    }:
        guard_output_grounding(
            payload,
            operation=operation,
            verified=verified_context,
            policy=policy or get_operation_policy(operation),
            source_text=source_text,
            user_id=user_id,
            offer_id=offer_id,
        )


def filter_allowed_fields(payload: dict[str, Any], operation: AiOperation) -> dict[str, Any]:
    allowed = allowed_fields_for(operation)
    if not allowed:
        return payload
    return {key: value for key, value in payload.items() if key in allowed}


def _always_allowed(operation: AiOperation) -> set[str]:
    if operation == AiOperation.GENERATE_OFFER:
        return {"draft", "recommendations"}
    if operation == AiOperation.EDIT_OFFER:
        return {"changes"}
    if operation in {
        AiOperation.IMPROVE_OFFER_TITLE,
        AiOperation.IMPROVE_OFFER_DESCRIPTION,
        AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
    }:
        return {"value"}
    return set()


def _check_lengths(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            limit = _MAX_FIELD.get(key)
            if limit and isinstance(value, str) and len(value) > limit:
                raise AiError("AI_INVALID_RESPONSE", "AI returned an invalid response", 502)
            _check_lengths(value)
    elif isinstance(payload, list):
        for item in payload:
            _check_lengths(item)


def _reject(
    operation: AiOperation,
    user_id: int | None,
    offer_id: str | int | None,
    text: str,
    reason: str,
) -> None:
    log_security_event(
        SecurityEvent.AI_OUTPUT_POLICY_VIOLATION,
        operation=operation,
        source=InputSource.AI_OUTPUT,
        category=reason,
        accepted=False,
        user_id=user_id,
        offer_id=offer_id,
        payload=text,
        extra={"blocked_stage": "OUTPUT_GUARD"},
    )
    raise AiError("AI_INVALID_RESPONSE", "AI returned an invalid response", 502)
