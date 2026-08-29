from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WebsiteContext:
    source_url: str
    status: str
    reason: str | None = None
    title: str | None = None
    description: str | None = None
    h1: str | None = None
    headings: list[str] = field(default_factory=list)
    main_text: str = ""
    product_name: str | None = None
    product_description: str | None = None
    price_hints: list[str] = field(default_factory=list)
    cta_hints: list[str] = field(default_factory=list)
    product_type_hint: str | None = None
    image_data_url: str | None = None
    image_source: str | None = None
    content_bytes: int = 0
    extracted_chars: int = 0

    @classmethod
    def unavailable(cls, source_url: str, reason: str = "unavailable") -> WebsiteContext:
        return cls(source_url=source_url, status="unavailable", reason=reason)

    def to_prompt(self) -> dict[str, Any]:
        if self.status != "ok":
            return {"status": "unavailable", "source_url": self.source_url}
        return {
            "status": "ok",
            "source_url": self.source_url,
            "title": self.title,
            "description": self.description,
            "h1": self.h1,
            "headings": self.headings,
            "main_text": self.main_text,
            "product_name": self.product_name,
            "product_description": self.product_description,
            "price_hints": self.price_hints,
            "cta_hints": self.cta_hints,
            "product_type_hint": self.product_type_hint,
            "image_found": bool(self.image_data_url),
        }
