from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai.safety.normalize import normalize_user_text

_NUMBER = re.compile(
    r"(?<![\w./])(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?%?(?![\w./])"
)
_URL = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.I)
_MONEY = re.compile(
    r"(?:₽|руб\.?|\$|€|usd|eur)\s*(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?"
    r"|(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?\s*(?:₽|руб\.?|\$|€|usd|eur)",
    re.I,
)
_PRESENTATION_ONLY = re.compile(r"^\d{1,2}$")  # list ordinals 1..99 alone are presentation


@dataclass(frozen=True)
class VerifiedContext:
    current_field: str
    current_value: str
    texts: tuple[str, ...] = ()
    numbers: frozenset[str] = field(default_factory=frozenset)
    urls: frozenset[str] = field(default_factory=frozenset)
    money_amounts: frozenset[str] = field(default_factory=frozenset)
    facts: tuple[str, ...] = ()

    def as_prompt_dict(self) -> dict[str, Any]:
        return {
            "currentField": self.current_field,
            "currentValue": self.current_value,
            "verifiedFacts": list(self.facts),
            "verifiedNumbers": sorted(self.numbers),
            "verifiedUrls": sorted(self.urls),
            "verifiedMoney": sorted(self.money_amounts),
            "note": "USER_GUIDANCE is not a verified fact source.",
        }


def extract_numbers(text: str | None) -> set[str]:
    values: set[str] = set()
    for match in _NUMBER.finditer(text or ""):
        token = match.group(0)
        values.add(_normalize_number(token))
    return {item for item in values if item}


def extract_urls(text: str | None) -> set[str]:
    return {match.group(0).rstrip(").,;]") for match in _URL.finditer(text or "")}


def extract_money(text: str | None) -> set[str]:
    return {_normalize_number(match.group(0)) for match in _MONEY.finditer(text or "")}


def build_verified_context(
    *,
    field: str,
    current_value: str | None,
    offer_context: dict[str, Any] | None = None,
    extra_texts: list[str] | None = None,
) -> VerifiedContext:
    context = offer_context or {}
    blobs: list[str] = []
    for key in (
        "name",
        "description",
        "category",
        "geo",
        "partner_notes",
        "product_url",
        "productName",
        "productDescription",
    ):
        value = context.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            blobs.extend(str(item) for item in value if item is not None)
        else:
            blobs.append(str(value))
    if current_value:
        blobs.append(str(current_value))
    for item in extra_texts or []:
        if item:
            blobs.append(str(item))

    # Commercial numbers from offer context are verified when present.
    for key in ("commission_value", "attribution_window_days"):
        value = context.get(key)
        if value is not None and value != "":
            blobs.append(str(value))

    joined = "\n".join(normalize_user_text(item) for item in blobs if item)
    numbers = extract_numbers(joined)
    urls = extract_urls(joined)
    money = extract_money(joined)
    facts = tuple(
        normalize_user_text(item) for item in blobs if item and normalize_user_text(item)
    )
    return VerifiedContext(
        current_field=field,
        current_value=normalize_user_text(current_value),
        texts=tuple(facts),
        numbers=frozenset(numbers),
        urls=frozenset(urls),
        money_amounts=frozenset(money),
        facts=facts,
    )


def _normalize_number(token: str) -> str:
    text = token.casefold().replace("\u00a0", " ").replace(" ", "")
    text = text.replace("руб.", "").replace("руб", "").replace("₽", "")
    text = text.replace("$", "").replace("€", "").replace("usd", "").replace("eur", "")
    text = text.replace("%", "")
    text = text.replace(",", ".")
    if text.endswith(".") and text.count(".") == 1:
        text = text[:-1]
    return text
