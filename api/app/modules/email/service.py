from app.modules.email.dto import EmailMessage
from app.modules.email.deps import get_email_provider
from app.modules.email.log import email_domain, log_email_error, logger
from app.modules.email.provider import EmailProvider
from app.modules.email.templates.account_confirmation import render_account_confirmation
from app.modules.email.templates.password_reset import render_password_reset


class EmailService:
    def __init__(self, provider: EmailProvider | None = None):
        self.provider = provider or get_email_provider()

    async def send_password_reset(self, *, to: str, reset_url: str, ttl_minutes: int) -> None:
        subject, text, html = render_password_reset(reset_url=reset_url, ttl_minutes=ttl_minutes)
        await self._deliver("password_reset", EmailMessage(to=to, subject=subject, text=text, html=html))

    async def send_account_confirmation(self, *, to: str, confirm_url: str, ttl_hours: int) -> None:
        subject, text, html = render_account_confirmation(
            confirm_url=confirm_url, ttl_hours=ttl_hours
        )
        await self._deliver(
            "account_confirmation",
            EmailMessage(to=to, subject=subject, text=text, html=html),
        )

    async def _deliver(self, kind: str, message: EmailMessage) -> None:
        to_domain = email_domain(message.to)
        logger.info("email_send_started", kind=kind, subject=message.subject, to_domain=to_domain)
        try:
            await self.provider.send(message)
        except Exception as exc:
            log_email_error("email_send_failed", exc, kind=kind, subject=message.subject, to_domain=to_domain)
            raise
        logger.info("email_send_succeeded", kind=kind, subject=message.subject, to_domain=to_domain)
