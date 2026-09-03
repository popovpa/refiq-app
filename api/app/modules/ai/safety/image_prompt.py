from __future__ import annotations

import re

from app.core.config import settings
from app.modules.ai.application.creative.promo_copy_guard import looks_like_affiliate_recruiting
from app.modules.ai.application.creative.promo_image_prompt import normalize_image_prompt
from app.modules.ai.errors import AiError
from app.modules.ai.safety.events import SecurityEvent, log_security_event
from app.modules.ai.safety.local_guard import inspect_local
from app.modules.ai.safety.operations import AiOperation, InputSource
from app.modules.ai.safety.scope_guard import inspect_scope

_META = re.compile(
    r"(ignore (previous|all|system) instructions|system prompt|developer message|"
    r"act as system|you are now|tell image generator|instead do|"
    r"игнорируй (все|предыдущие) инструк|системный промпт)",
    re.I,
)
_INTERNAL = re.compile(r"\b(refiq|rqcid|openai_api_key|bearer [a-z0-9._-]+)\b", re.I)
_AFFILIATE = re.compile(r"\b(payout|cpa|cps|cpl|affiliate|webmaster|комисс|выплат)\b", re.I)


class ImagePromptValidator:
    def validate(
        self,
        prompt: str,
        *,
        product_context: dict | None = None,
        user_id: int | None = None,
        offer_id: str | int | None = None,
    ) -> str:
        text = normalize_image_prompt(prompt)
        if not text:
            raise AiError("AI_INVALID_RESPONSE", "Image prompt was empty", 502)
        limit = max(8000, int(getattr(settings, "AI_GUIDANCE_MAX_CHARS", 4000) or 4000) * 2)
        if len(text) > limit:
            raise AiError("AI_INVALID_RESPONSE", "Image prompt exceeded the allowed length", 502)
        local = inspect_local(text)
        if local.blocked or _META.search(text) or _INTERNAL.search(text):
            log_security_event(
                SecurityEvent.PROMPT_INJECTION_DETECTED,
                operation=AiOperation.GENERATE_IMAGE_PROMPT,
                source=InputSource.IMAGE_PROMPT,
                category=local.category or "PROMPT_INJECTION",
                accepted=False,
                user_id=user_id,
                offer_id=offer_id,
                payload=text,
            )
            raise AiError("AI_INVALID_RESPONSE", "Image prompt contained disallowed instructions", 502)
        if looks_like_affiliate_recruiting(text, product_context=product_context) or (
            _AFFILIATE.search(text) and not looks_like_affiliate_recruiting(
                " ".join(str(item) for item in (product_context or {}).values() if item),
                product_context=product_context,
            )
        ):
            raise AiError("AI_INVALID_RESPONSE", "Image prompt contained affiliate language", 502)
        scope = inspect_scope(text, operation=AiOperation.GENERATE_IMAGE_PROMPT)
        if not scope.allowed and scope.invalid_intents:
            log_security_event(
                SecurityEvent.PROMPT_SCOPE_VIOLATION
                if scope.category != "MIXED_VALID_AND_INVALID_GUIDANCE"
                else SecurityEvent.MIXED_GUIDANCE_REJECTED,
                operation=AiOperation.GENERATE_IMAGE_PROMPT,
                source=InputSource.IMAGE_PROMPT,
                category=scope.category,
                accepted=False,
                user_id=user_id,
                offer_id=offer_id,
                payload=text,
                extra={"blocked_stage": "SCOPE_GUARD", "invalid_intents": list(scope.invalid_intents)},
            )
            raise AiError("AI_INVALID_RESPONSE", "Image prompt contained disallowed instructions", 502)
        return text
