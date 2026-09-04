from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.modules.ai.errors import AiError
from app.modules.ai.safety.events import SecurityEvent, log_security_event
from app.modules.ai.safety.operations import AiOperation, InputSource
from app.modules.ai.safety.policy import AiOperationPolicy, get_operation_policy
from app.modules.ai.safety.verified_context import (
    VerifiedContext,
    extract_money,
    extract_numbers,
    extract_urls,
)

_SUSPICIOUS_CLAIMS = (
    "№1",
    "номер 1",
    "лучший в",
    "гарантированный результат",
    "официальный дилер",
    "сертифицировано",
    "100% безопасно",
    "без риска",
    "лечит",
)


@dataclass(frozen=True)
class GroundingResult:
    grounded: bool
    unsupported_numbers: tuple[str, ...] = ()
    unsupported_urls: tuple[str, ...] = ()
    unsupported_money: tuple[str, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    reason_code: str = "OK"


def output_grounding_enabled() -> bool:
    return bool(getattr(settings, "AI_OUTPUT_GROUNDING_ENABLED", True))


def _flatten_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def inspect_output_grounding(
    payload,
    *,
    operation: AiOperation,
    verified: VerifiedContext | None,
    policy: AiOperationPolicy | None = None,
    source_text: str | None = None,
) -> GroundingResult:
    if not output_grounding_enabled() or verified is None:
        return GroundingResult(True)
    policy = policy or get_operation_policy(operation)
    if policy.allow_new_facts and policy.allow_new_numbers and policy.allow_new_urls:
        return GroundingResult(True)

    text = _flatten_text(payload)
    source_blob = "\n".join([verified.current_value, source_text or "", *verified.texts])
    source_numbers = set(verified.numbers) | extract_numbers(source_blob)
    source_urls = set(verified.urls) | extract_urls(source_blob)
    source_money = set(verified.money_amounts) | extract_money(source_blob)

    out_numbers = extract_numbers(text)
    out_urls = extract_urls(text)
    out_money = extract_money(text)

    unsupported_numbers: list[str] = []
    if not policy.allow_new_numbers:
        for number in sorted(out_numbers - source_numbers):
            if policy.strict_title_numbers or not _is_presentation_number(number, text):
                unsupported_numbers.append(number)

    unsupported_urls = sorted(out_urls - source_urls) if not policy.allow_new_urls else []
    unsupported_money = sorted(out_money - source_money) if not policy.allow_new_facts else []

    unsupported_claims: list[str] = []
    lowered = text.casefold()
    source_lower = source_blob.casefold()
    if not policy.allow_new_facts:
        for claim in _SUSPICIOUS_CLAIMS:
            if claim in lowered and claim not in source_lower:
                unsupported_claims.append(claim)

    if unsupported_numbers or unsupported_urls or unsupported_money or unsupported_claims:
        reason = "AI_OUTPUT_NEW_NUMBER" if unsupported_numbers else "AI_OUTPUT_UNGROUNDED"
        if unsupported_urls:
            reason = "AI_OUTPUT_NEW_URL"
        if unsupported_money:
            reason = "AI_OUTPUT_NEW_NUMBER"
        return GroundingResult(
            False,
            tuple(unsupported_numbers),
            tuple(unsupported_urls),
            tuple(unsupported_money),
            tuple(unsupported_claims),
            reason,
        )
    return GroundingResult(True)


def guard_output_grounding(
    payload,
    *,
    operation: AiOperation,
    verified: VerifiedContext | None,
    policy: AiOperationPolicy | None = None,
    source_text: str | None = None,
    user_id: int | None = None,
    offer_id: str | int | None = None,
) -> None:
    result = inspect_output_grounding(
        payload,
        operation=operation,
        verified=verified,
        policy=policy,
        source_text=source_text,
    )
    if result.grounded:
        return
    event = SecurityEvent.AI_OUTPUT_UNGROUNDED
    if result.reason_code == "AI_OUTPUT_NEW_NUMBER":
        event = SecurityEvent.AI_OUTPUT_NEW_NUMBER
    elif result.reason_code == "AI_OUTPUT_NEW_URL":
        event = SecurityEvent.AI_OUTPUT_NEW_URL
    elif result.reason_code == "AI_OUTPUT_NEW_ENTITY":
        event = SecurityEvent.AI_OUTPUT_NEW_ENTITY
    log_security_event(
        event,
        operation=operation,
        source=InputSource.AI_OUTPUT,
        category=result.reason_code,
        accepted=False,
        user_id=user_id,
        offer_id=offer_id,
        payload=_flatten_text(payload),
        extra={
            "blocked_stage": "OUTPUT_GUARD",
            "unsupported_numbers": list(result.unsupported_numbers),
            "unsupported_urls": list(result.unsupported_urls),
            "unsupported_money": list(result.unsupported_money),
            "unsupported_claims": list(result.unsupported_claims),
        },
    )
    raise AiError("AI_INVALID_RESPONSE", "AI returned an invalid response", 502)


def _is_presentation_number(number: str, text: str) -> bool:
    """Allow simple list ordinals like '1.' / '2)' in longer descriptions."""
    if not re.fullmatch(r"\d{1,2}", number):
        return False
    return bool(re.search(rf"(?:^|\n)\s*{re.escape(number)}[.)]\s+\S", text))
