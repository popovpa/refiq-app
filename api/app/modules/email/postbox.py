from __future__ import annotations

import asyncio

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.modules.email.dto import EmailMessage
from app.modules.email.errors import EmailNotConfigured, EmailSendError
from app.modules.email.log import email_domain, log_email_error


class YandexCloudPostboxProvider:
    """Sends mail through Yandex Cloud Postbox Amazon-compatible API (not SMTP)."""

    def __init__(self):
        if not settings.postbox_enabled:
            raise EmailNotConfigured("Yandex Cloud Postbox is not configured")
        self._from = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        timeout = max(1.0, min(settings.EMAIL_SEND_TIMEOUT_SECONDS, 15.0))
        self._client = boto3.client(
            "sesv2",
            endpoint_url=settings.YANDEX_POSTBOX_ENDPOINT,
            region_name=settings.YANDEX_POSTBOX_REGION,
            aws_access_key_id=settings.YANDEX_POSTBOX_ACCESS_KEY_ID,
            aws_secret_access_key=settings.YANDEX_POSTBOX_SECRET_ACCESS_KEY,
            config=Config(
                connect_timeout=min(3.0, timeout),
                read_timeout=timeout,
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )

    async def send(self, message: EmailMessage) -> None:
        try:
            await asyncio.to_thread(self._send, message)
        except EmailSendError:
            raise
        except Exception as exc:
            log_email_error("email_send_failed", exc, to_domain=email_domain(message.to))
            raise EmailSendError("Failed to send email") from exc

    def _send(self, message: EmailMessage) -> None:
        try:
            self._client.send_email(
                FromEmailAddress=self._from,
                Destination={"ToAddresses": [message.to]},
                Content={
                    "Simple": {
                        "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": message.text, "Charset": "UTF-8"},
                            "Html": {"Data": message.html, "Charset": "UTF-8"},
                        },
                    }
                },
            )
        except (ClientError, BotoCoreError) as exc:
            details = _postbox_error_fields(exc)
            log_email_error("postbox_send_failed", exc, to_domain=email_domain(message.to), **details)
            raise EmailSendError("Failed to send email") from exc


def _postbox_error_fields(exc: Exception) -> dict:
    fields: dict[str, str | None] = {}
    if isinstance(exc, ClientError):
        error = (exc.response or {}).get("Error") or {}
        fields["error_code"] = error.get("Code")
        fields["error_message"] = error.get("Message")
    return fields
