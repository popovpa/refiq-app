from urllib.parse import urlparse

from app.core.exceptions import AppError

INVALID_SITE_URL = AppError("INVALID_SITE_URL", "Введите корректный URL сайта", 400)


def normalize_site_input(raw: str | None) -> tuple[str, str]:
    """Return (domain, suggested_name) from a user-entered URL or hostname."""
    value = (raw or "").strip()
    if not value or any(ch.isspace() for ch in value):
        raise INVALID_SITE_URL
    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise INVALID_SITE_URL from exc
    if parsed.scheme not in {"http", "https"}:
        raise INVALID_SITE_URL
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or "." not in hostname:
        raise INVALID_SITE_URL
    if hostname.startswith("[") or ":" in hostname:
        raise INVALID_SITE_URL
    return hostname, hostname


def hostname_from_url(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or "." not in hostname:
        return None
    return hostname
