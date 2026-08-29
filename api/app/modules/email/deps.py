from __future__ import annotations

from app.modules.email.errors import EmailNotConfigured
from app.modules.email.log import log_email_error
from app.modules.email.provider import EmailProvider

_provider: EmailProvider | None = None


class DisabledEmailProvider:
    async def send(self, message) -> None:
        exc = EmailNotConfigured("Email provider is not configured")
        log_email_error(
            "email_not_configured",
            exc,
            subject=getattr(message, "subject", None),
        )
        raise exc


def get_email_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        from app.core.config import settings
        from app.modules.email.postbox import YandexCloudPostboxProvider

        _provider = YandexCloudPostboxProvider() if settings.postbox_enabled else DisabledEmailProvider()
    return _provider


def set_email_provider(provider: EmailProvider | None) -> None:
    global _provider
    _provider = provider
