from __future__ import annotations

import re
import unicodedata

from app.core.config import settings

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
CONTROL_ALLOWED = {"\n", "\t"}
_REPEAT_CHAR = re.compile(r"(.)\1{19,}")
_REPEAT_WORD = re.compile(r"(\b\w{1,32}\b)(?:\s+\1){4,}", re.IGNORECASE)
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_NEWLINES = re.compile(r"\n{3,}")


def guidance_max_chars() -> int:
    return max(32, int(getattr(settings, "AI_GUIDANCE_MAX_CHARS", 4000) or 4000))


def normalize_user_text(value: str | None, *, max_chars: int | None = None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.translate(ZERO_WIDTH)
    text = "".join(ch for ch in text if (ch in CONTROL_ALLOWED or unicodedata.category(ch)[0] != "C"))
    text = _REPEAT_CHAR.sub(lambda match: match.group(1) * 20, text)
    text = _REPEAT_WORD.sub(r"\1 \1 \1", text)
    text = _WHITESPACE.sub(" ", text)
    text = _NEWLINES.sub("\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = text.strip()
    limit = guidance_max_chars() if max_chars is None else max_chars
    if limit and len(text) > limit:
        text = text[:limit].rstrip()
    return text


def fold_for_match(value: str) -> str:
    text = normalize_user_text(value)
    text = text.casefold()
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return _WHITESPACE.sub(" ", text).strip()
