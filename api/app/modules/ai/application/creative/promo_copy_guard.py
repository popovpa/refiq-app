from __future__ import annotations

import re
from typing import Any

from app.modules.ai.errors import AiError

_ECONOMICS_PATTERNS = [
    re.compile(r"получайте комисси", re.I),
    re.compile(r"заработ\w*.{0,40}комисс", re.I),
    re.compile(r"комисси\w*.{0,40}за (кажд|продаж|заявк|лид)", re.I),
    re.compile(r"\bкомисс", re.I),
    re.compile(r"\b(cpa|cps|cpl)\b", re.I),
    re.compile(r"\bpayout\b", re.I),
    re.compile(r"вебмастер", re.I),
    re.compile(r"условия выплаты", re.I),
    re.compile(r"атрибуц", re.I),
    re.compile(r"разреш[её]нн\w+\s+(источник|трафик)", re.I),
    re.compile(r"запрещ[её]нн\w+\s+(источник|трафик)", re.I),
    re.compile(r"за каждый проданн", re.I),
    re.compile(r"\d[\d\s]{2,}\s*₽.{0,40}за продаж", re.I),
    re.compile(r"\brefiq\b", re.I),
    re.compile(r"партн[её]рская ссылка", re.I),
    re.compile(r"qr партн", re.I),
    re.compile(r"стать партн", re.I),
    re.compile(r"подключ\w+\s+оффер", re.I),
    re.compile(r"заработ\w+\s+\d", re.I),
]

_PROGRAM_PATTERNS = [
    re.compile(r"партн[её]рская программа", re.I),
    re.compile(r"реферальная программа", re.I),
    re.compile(r"привлекайте покупател", re.I),
    re.compile(r"привлечен\w+ покупател", re.I),
]


def looks_like_affiliate_recruiting(
    text: str,
    *,
    product_context: dict[str, Any] | None = None,
    include_program: bool = True,
) -> bool:
    blob = (text or "").strip()
    if not blob:
        return False
    allowed = _product_blob(product_context)
    patterns = list(_ECONOMICS_PATTERNS)
    if include_program:
        patterns.extend(_PROGRAM_PATTERNS)
    for pattern in patterns:
        if pattern.search(blob) and not pattern.search(allowed):
            return True
    return False


def strip_affiliate_language(
    text: str,
    *,
    product_context: dict[str, Any] | None = None,
    include_program: bool = True,
) -> str:
    blob = (text or "").strip()
    if not blob:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", blob) if part.strip()]
    kept = [
        part
        for part in parts
        if not looks_like_affiliate_recruiting(
            part, product_context=product_context, include_program=include_program
        )
    ]
    return " ".join(kept).strip()


def assert_customer_facing_copy(payload: Any, *, product_context: dict[str, Any] | None = None) -> None:
    text = _flatten(payload)
    if looks_like_affiliate_recruiting(text, product_context=product_context):
        raise AiError(
            "AI_INVALID_RESPONSE",
            "Generated copy advertised the affiliate program instead of the product",
            502,
        )


def _product_blob(product_context: dict[str, Any] | None) -> str:
    if not product_context:
        return ""
    parts = [
        product_context.get("name"),
        product_context.get("description"),
        product_context.get("category"),
    ]
    parts.extend(product_context.get("verifiedFacts") or [])
    return " ".join(str(item) for item in parts if item)


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(item) for item in value)
    return str(value)
