from __future__ import annotations

import re


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:—–])\s+")
_WHITESPACE = re.compile(r"\s+")


def normalize_image_prompt(prompt: str) -> str:
    return _WHITESPACE.sub(" ", (prompt or "").strip())


def compact_image_prompt_to_limit(prompt: str, *, limit: int) -> str:
    """Keep complete sentences, then clauses, then words. Never mid-word cut."""
    text = normalize_image_prompt(prompt)
    if limit <= 0 or len(text) <= limit:
        return text
    compacted = _join_until(_SENTENCE_SPLIT.split(text), limit)
    if compacted:
        return compacted
    compacted = _join_until(_CLAUSE_SPLIT.split(text), limit)
    if compacted:
        return compacted
    words = text.split(" ")
    compacted = _join_until(words, limit, sep=" ")
    if compacted:
        return compacted.rstrip(" ,;:—–-")
    return ""


def _join_until(parts: list[str], limit: int, *, sep: str = " ") -> str:
    acc: list[str] = []
    for part in parts:
        piece = (part or "").strip()
        if not piece:
            continue
        candidate = sep.join(acc + [piece]) if acc else piece
        if len(candidate) > limit:
            break
        acc.append(piece)
    return sep.join(acc).strip() if acc else ""
