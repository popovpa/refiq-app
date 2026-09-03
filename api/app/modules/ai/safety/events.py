from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import structlog

from app.modules.ai.safety.operations import AiOperation, InputSource

logger = structlog.get_logger()


class SecurityEvent(StrEnum):
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    PROMPT_SCOPE_VIOLATION = "PROMPT_SCOPE_VIOLATION"
    SYSTEM_PROMPT_EXTRACTION_ATTEMPT = "SYSTEM_PROMPT_EXTRACTION_ATTEMPT"
    SECRET_EXTRACTION_ATTEMPT = "SECRET_EXTRACTION_ATTEMPT"
    AI_OUTPUT_SCHEMA_VIOLATION = "AI_OUTPUT_SCHEMA_VIOLATION"
    AI_OUTPUT_POLICY_VIOLATION = "AI_OUTPUT_POLICY_VIOLATION"
    INDIRECT_INJECTION_DETECTED = "INDIRECT_INJECTION_DETECTED"


_CATEGORY_EVENTS = {
    "PROMPT_INJECTION": SecurityEvent.PROMPT_INJECTION_DETECTED,
    "OUT_OF_SCOPE": SecurityEvent.PROMPT_SCOPE_VIOLATION,
    "SYSTEM_PROMPT_EXTRACTION": SecurityEvent.SYSTEM_PROMPT_EXTRACTION_ATTEMPT,
    "SECRET_EXTRACTION": SecurityEvent.SECRET_EXTRACTION_ATTEMPT,
    "ROLE_OVERRIDE": SecurityEvent.PROMPT_INJECTION_DETECTED,
}


def event_for_category(category: str | None) -> SecurityEvent:
    return _CATEGORY_EVENTS.get((category or "").upper(), SecurityEvent.PROMPT_INJECTION_DETECTED)


def safe_payload_fingerprint(value: str | None, *, limit: int = 80) -> dict[str, Any]:
    text = value or ""
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    preview = text[:limit].replace("\n", " ")
    return {
        "payload_hash": digest,
        "payload_preview": preview,
        "payload_chars": len(text),
    }


def log_security_event(
    event: SecurityEvent,
    *,
    operation: AiOperation | str,
    source: InputSource | str,
    category: str | None = None,
    accepted: bool,
    user_id: int | None = None,
    offer_id: str | int | None = None,
    provider: str | None = None,
    model: str | None = None,
    payload: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    record = {
        "ai_security_event": event.value,
        "operation": operation.value if isinstance(operation, AiOperation) else operation,
        "source": source.value if isinstance(source, InputSource) else source,
        "category": category,
        "accepted": accepted,
        "user_id": user_id,
        "offer_id": str(offer_id) if offer_id is not None else None,
        "provider": provider,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **safe_payload_fingerprint(payload),
        **(extra or {}),
    }
    logger.warning("ai_security_event", **record)
