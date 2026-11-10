"""Click source attribution.

Priority for a registered click:
1. Tracking link traffic_source, normalized by the catalog.
2. Referer hostname when the link has no source.
3. Direct visit when both are empty.

Paid click ids and UTM from the browser are not mixed into this label.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.modules.catalog.traffic import TRAFFIC_SOURCES, normalize_traffic_source

_LABELS = {code: label for code, label, _en, _group in TRAFFIC_SOURCES}

_PLATFORMS = (
    ("yandex", "Яндекс"),
    ("google", "Google"),
    ("vkontakte", "VK"),
    ("vk.com", "VK"),
    ("vk.ru", "VK"),
    ("telegram", "Telegram"),
    ("t.me", "Telegram"),
    ("tiktok", "TikTok"),
)


def catalog_label(code: str | None) -> str | None:
    normalized = normalize_traffic_source(code)
    if not normalized:
        return None
    return _LABELS.get(normalized)


def _platform(value: str | None) -> tuple[str, str] | None:
    text = (value or "").strip().lower()
    if not text:
        return None
    for needle, label in _PLATFORMS:
        if needle in text:
            key = label.lower()
            return key, label
    return None


def referer_host(referer: str | None) -> str:
    text = (referer or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"//{text}")
    return (parsed.hostname or "").lower()


def classify_source(traffic_source: str | None, referer: str | None = None) -> tuple[str, str, str]:
    """Return key, label and kind: tracking_link, referrer, direct or unknown."""

    raw = (traffic_source or "").strip()
    if raw:
        platform = _platform(raw)
        normalized = normalize_traffic_source(raw)
        if normalized:
            return normalized, _LABELS.get(normalized, raw), "tracking_link"
        if platform:
            return platform[0], platform[1], "tracking_link"
        return raw.lower(), raw, "tracking_link"

    host = referer_host(referer)
    if host:
        platform = _platform(host)
        if platform:
            return platform[0], platform[1], "referrer"
        return host, host, "referrer"
    if referer is not None and not (referer or "").strip() and not raw:
        return "direct", "Прямой заход", "direct"
    return "unknown", "Источник не указан", "unknown"


def normalize_page(path: str | None) -> str:
    text = (path or "").strip()
    if not text:
        return ""
    base, _, query = text.partition("?")
    if not query:
        return base or "/"
    kept = []
    for part in query.split("&"):
        name = part.split("=", 1)[0].lower()
        if name in {
            "rqcid",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "yclid",
            "gclid",
            "fbclid",
            "ttclid",
            "vk_click_id",
            "gbraid",
            "wbraid",
        }:
            continue
        if part:
            kept.append(part)
    if not kept:
        return base or "/"
    return f"{base}?{'&'.join(kept)}"
