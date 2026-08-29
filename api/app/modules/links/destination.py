from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.system.models import BusinessSettings

TRACKER_HOSTS = frozenset({"go.refiq.ru", "www.go.refiq.ru"})
ALLOWED_SCHEMES = frozenset({"https", "http"})
DESTINATION_MAX_LENGTH = 500


def validate_destination_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400)
    if len(value) > DESTINATION_MAX_LENGTH:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400)

    parsed = urlparse(value)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or "." not in hostname:
        raise AppError("INVALID_DESTINATION_URL", "Введите корректный URL", 400)
    if hostname in TRACKER_HOSTS or hostname.endswith(".go.refiq.ru"):
        raise AppError(
            "DESTINATION_DOMAIN_FORBIDDEN",
            "Этот домен нельзя использовать для данной ссылки",
            400,
        )
    return value


async def assert_destination_allowed(
    db: AsyncSession,
    *,
    business_id: int,
    url: str,
) -> str:
    normalized = validate_destination_url(url)
    hostname = (urlparse(normalized).hostname or "").lower().rstrip(".")
    row = (
        await db.execute(select(BusinessSettings).where(BusinessSettings.business_id == business_id))
    ).scalar_one_or_none()
    allowed = (row.settings or {}).get("verified_domains") if row and row.settings else None
    if allowed:
        hosts = {str(item).lower().rstrip(".") for item in allowed if item}
        if hostname not in hosts and not any(hostname.endswith(f".{item}") for item in hosts):
            raise AppError(
                "DESTINATION_DOMAIN_FORBIDDEN",
                "Этот домен нельзя использовать для данной ссылки",
                400,
            )
    return normalized
