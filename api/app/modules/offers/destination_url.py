"""URL safety for offer landing pages.

Reuses link destination checks and the existing SSRF helpers. Query strings are
kept: `/product.html?id=nova-max` and `/product.html?id=pulse-se` are different pages.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.exceptions import AppError
from app.modules.ai.website.ssrf import UnsafeUrlError, ensure_public_host, parse_public_url
from app.modules.links.destination import validate_destination_url

DOCUMENTATION_HOSTS = frozenset({"example.com", "example.org", "example.net", "example.edu"})
DOCUMENTATION_SUFFIXES = (".example", ".invalid", ".test", ".example.com", ".example.org", ".example.net")


def _is_documentation_host(host: str) -> bool:
    if host in DOCUMENTATION_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in DOCUMENTATION_SUFFIXES)


async def validate_destination_page_url(raw: str | None) -> str:
    normalized = validate_destination_url(raw)
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise AppError("DESTINATION_HTTPS_REQUIRED", "Для посадочной страницы нужен HTTPS.", 400)
    if parsed.username or parsed.password:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400)
    if parsed.port not in (None, 443):
        raise AppError("DESTINATION_PORT_FORBIDDEN", "Этот порт нельзя использовать для посадочной страницы.", 400)
    try:
        _url, host = parse_public_url(normalized)
    except UnsafeUrlError as exc:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400) from exc
    if not _is_documentation_host(host):
        try:
            await ensure_public_host(host)
        except UnsafeUrlError as exc:
            raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400) from exc
    return normalized


async def validate_destination_image_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return await validate_destination_page_url(text)
