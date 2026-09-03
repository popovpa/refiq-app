from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.modules.ai.errors import AiError
from app.modules.ai.safety.events import SecurityEvent, event_for_category, log_security_event
from app.modules.ai.safety.local_guard import DECISION_ALLOW, DECISION_BLOCK, inspect_local
from app.modules.ai.safety.normalize import normalize_user_text
from app.modules.ai.safety.operations import (
    AiOperation,
    InputSource,
    SECURITY_SENSITIVE_OPERATIONS,
    normalize_preset,
)
from app.modules.ai.safety.policy import get_operation_policy
from app.modules.ai.safety.scope_guard import inspect_scope
from app.modules.ai.safety.semantic_guard import (
    classify_guidance,
    is_false_style_conflict,
    semantic_guard_enabled,
    user_facing_rejection_reason,
)
from app.modules.ai.safety.trusted_prompt import compose_guidance

INVALID_GUIDANCE_MESSAGE = (
    "Не удалось применить пожелание. Используйте поле для изменения стиля, длины, структуры или акцентов текста. "
    "Фактические данные изменяйте в полях оффера."
)
INVALID_OFFER_GUIDANCE_MESSAGE = INVALID_GUIDANCE_MESSAGE


def invalid_ai_guidance(message: str | None = None) -> AiError:
    return AiError("INVALID_AI_GUIDANCE", message or INVALID_GUIDANCE_MESSAGE, 400)


@dataclass(frozen=True)
class EvaluatedGuidance:
    operation: AiOperation
    preset: str | None
    guidance: str
    composed: str


def resolve_guidance_fields(
    *,
    instruction: str | None = None,
    guidance: str | None = None,
    preset: str | None = None,
) -> tuple[str | None, str]:
    return normalize_preset(preset), normalize_user_text(guidance or instruction or "")


async def evaluate_user_guidance(
    *,
    operation: AiOperation,
    instruction: str | None = None,
    guidance: str | None = None,
    preset: str | None = None,
    user_id: int | None = None,
    offer_id: str | int | None = None,
    source: InputSource = InputSource.USER_GUIDANCE,
    require_input: bool = True,
    message: str | None = None,
) -> EvaluatedGuidance:
    policy = get_operation_policy(operation)
    preset_id, text = resolve_guidance_fields(instruction=instruction, guidance=guidance, preset=preset)
    if require_input and not preset_id and not text:
        raise invalid_ai_guidance(message)
    local = inspect_local(text)
    if text and local.decision == DECISION_BLOCK:
        log_security_event(
            event_for_category(local.category),
            operation=operation,
            source=source,
            category=local.category,
            accepted=False,
            user_id=user_id,
            offer_id=offer_id,
            payload=text,
            extra={"layer": "local", "blocked_stage": "INPUT_GUARD"},
        )
        raise invalid_ai_guidance(message)
    if text:
        scope = inspect_scope(text, operation=operation, policy=policy)
        if not scope.allowed:
            log_security_event(
                event_for_category(scope.category),
                operation=operation,
                source=source,
                category=scope.category,
                accepted=False,
                user_id=user_id,
                offer_id=offer_id,
                payload=text,
                extra={
                    "layer": "scope",
                    "blocked_stage": "SCOPE_GUARD",
                    "reason_code": scope.reason_code,
                    "valid_intents": list(scope.valid_intents),
                    "invalid_intents": list(scope.invalid_intents),
                    "user_message": scope.message,
                },
            )
            raise invalid_ai_guidance(scope.message)
    if text and _should_classify(text, preset_id, local.decision, operation):
        await _run_semantic(
            text,
            operation=operation,
            preset=preset_id,
            user_id=user_id,
            offer_id=offer_id,
            source=source,
            message=message,
        )
    return EvaluatedGuidance(
        operation=operation,
        preset=preset_id,
        guidance=text,
        composed=compose_guidance(preset=preset_id, guidance=text),
    )


def inspect_untrusted_text(
    text: str | None,
    *,
    operation: AiOperation,
    source: InputSource,
    user_id: int | None = None,
    offer_id: str | int | None = None,
) -> str:
    normalized = normalize_user_text(text)
    if not normalized:
        return ""
    local = inspect_local(normalized)
    if local.decision != DECISION_ALLOW:
        event = (
            SecurityEvent.INDIRECT_INJECTION_DETECTED
            if source in {InputSource.LANDING_PAGE, InputSource.EXTERNAL_CONTENT, InputSource.OFFER_FIELD}
            else event_for_category(local.category)
        )
        log_security_event(
            event,
            operation=operation,
            source=source,
            category=local.category,
            accepted=True,
            user_id=user_id,
            offer_id=offer_id,
            payload=normalized,
            extra={"layer": "local", "persistent": source != InputSource.USER_GUIDANCE},
        )
    return normalized


def _should_classify(text: str, preset: str | None, decision: str, operation: AiOperation) -> bool:
    if not semantic_guard_enabled():
        return False
    if not text:
        return False
    if decision != DECISION_ALLOW:
        return True
    if preset and text == compose_guidance(preset=preset, guidance=""):
        return False
    return operation in SECURITY_SENSITIVE_OPERATIONS


async def _run_semantic(
    text: str,
    *,
    operation: AiOperation,
    preset: str | None,
    user_id: int | None,
    offer_id: str | int | None,
    source: InputSource,
    message: str | None,
) -> None:
    fail_closed = operation in SECURITY_SENSITIVE_OPERATIONS and bool(
        getattr(settings, "AI_SEMANTIC_GUARD_FAIL_CLOSED", True)
    )
    try:
        result = await classify_guidance(guidance=text, operation=operation, preset=preset)
    except Exception:
        log_security_event(
            SecurityEvent.PROMPT_SCOPE_VIOLATION,
            operation=operation,
            source=source,
            category="UNKNOWN",
            accepted=False,
            user_id=user_id,
            offer_id=offer_id,
            payload=text,
            extra={"layer": "semantic", "reason": "guard_failed", "blocked_stage": "SCOPE_GUARD"},
        )
        if fail_closed:
            raise invalid_ai_guidance(message)
        return
    if result.invalid_intents:
        detail = user_facing_rejection_reason(result, fallback=message or INVALID_GUIDANCE_MESSAGE)
        log_security_event(
            event_for_category(
                "MIXED_VALID_AND_INVALID_GUIDANCE" if result.valid_intents else result.category
            ),
            operation=operation,
            source=source,
            category="MIXED_VALID_AND_INVALID_GUIDANCE" if result.valid_intents else result.category,
            accepted=False,
            user_id=user_id,
            offer_id=offer_id,
            payload=text,
            extra={
                "layer": "semantic",
                "blocked_stage": "SCOPE_GUARD",
                "reason_code": result.reason_code,
                "valid_intents": list(result.valid_intents),
                "invalid_intents": list(result.invalid_intents),
                "user_message": detail,
            },
        )
        raise invalid_ai_guidance(detail)
    if result.allowed and result.category == "VALID_GUIDANCE":
        return
    if is_false_style_conflict(result, text):
        return
    fallback = message or INVALID_GUIDANCE_MESSAGE
    detail = user_facing_rejection_reason(result, fallback=fallback)
    log_security_event(
        event_for_category(result.category),
        operation=operation,
        source=source,
        category=result.category,
        accepted=False,
        user_id=user_id,
        offer_id=offer_id,
        payload=text,
        extra={
            "layer": "semantic",
            "blocked_stage": "SCOPE_GUARD",
            "reason_code": result.reason_code,
            "user_message": detail,
        },
    )
    raise invalid_ai_guidance(detail)
