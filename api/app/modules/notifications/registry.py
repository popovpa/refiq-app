from collections.abc import Callable
from typing import Any

from app.modules.notifications.enums import NotificationSeverity, NotificationType

DestinationBuilder = Callable[[dict[str, Any]], str | None]


def _site_destination(metadata: dict[str, Any]) -> str:
    site_id = metadata.get("site_id")
    if site_id:
        return f"/business/settings?tab=sites&site={site_id}"
    return "/business/settings?tab=sites"


def _postback_destination(_metadata: dict[str, Any]) -> str:
    return "/business/settings?tab=integrations&integration=postback"


def _payout_destination(_metadata: dict[str, Any]) -> str:
    return "/business/payouts"


NOTIFICATION_TYPE_REGISTRY: dict[NotificationType, dict[str, Any]] = {
    NotificationType.SDK_CONNECTED: {
        "title": "SDK успешно подключён",
        "severity": NotificationSeverity.SUCCESS,
        "destination": _site_destination,
    },
    NotificationType.SDK_EVENTS_STOPPED: {
        "title": "SDK перестал передавать события",
        "severity": NotificationSeverity.WARNING,
        "destination": _site_destination,
    },
    NotificationType.POSTBACK_FAILED: {
        "title": "Postback не проходит",
        "severity": NotificationSeverity.CRITICAL,
        "destination": _postback_destination,
    },
    NotificationType.POSTBACK_HIGH_ERROR_RATE: {
        "title": "Высокий процент ошибочных postback",
        "severity": NotificationSeverity.WARNING,
        "destination": _postback_destination,
    },
    NotificationType.SITE_DOMAIN_VERIFIED: {
        "title": "Домен сайта подтверждён",
        "severity": NotificationSeverity.SUCCESS,
        "destination": _site_destination,
    },
    NotificationType.SITE_VERIFICATION_FAILED: {
        "title": "Проверка сайта не пройдена",
        "severity": NotificationSeverity.CRITICAL,
        "destination": _site_destination,
    },
    NotificationType.PAYOUT_DUE: {
        "title": "Подтвердите выплату партнёру",
        "severity": NotificationSeverity.WARNING,
        "destination": _payout_destination,
    },
    NotificationType.PAYOUT_REMINDER: {
        "title": "Напоминание о выплате партнёру",
        "severity": NotificationSeverity.WARNING,
        "destination": _payout_destination,
    },
    NotificationType.PAYOUT_OVERDUE: {
        "title": "Просрочена выплата партнёру",
        "severity": NotificationSeverity.CRITICAL,
        "destination": _payout_destination,
    },
    NotificationType.PARTNER_TRAFFIC_SUSPENDED: {
        "title": "Партнёрский трафик приостановлен",
        "severity": NotificationSeverity.CRITICAL,
        "destination": _payout_destination,
    },
}


def resolve_notification_type(value: str) -> NotificationType:
    return NotificationType(value)


def type_config(notification_type: NotificationType | str) -> dict[str, Any]:
    typed = notification_type if isinstance(notification_type, NotificationType) else NotificationType(notification_type)
    return NOTIFICATION_TYPE_REGISTRY[typed]


def default_title(notification_type: NotificationType | str) -> str:
    return type_config(notification_type)["title"]


def default_severity(notification_type: NotificationType | str) -> NotificationSeverity:
    return type_config(notification_type)["severity"]


def default_destination(notification_type: NotificationType | str, metadata: dict[str, Any] | None) -> str | None:
    builder: DestinationBuilder = type_config(notification_type)["destination"]
    return builder(metadata or {})
