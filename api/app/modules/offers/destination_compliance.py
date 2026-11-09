"""Landing pages inherit the offer vertical. They do not open a second publication path.

Gambling categories cannot be published as destinations.
Betting categories stay restricted: OPEN access cannot gain a promotable page.
"""

from __future__ import annotations

from app.common.enums import AccessPolicy
from app.core.exceptions import AppError
from app.modules.offers.models import Offer

GAMBLING_CATEGORIES = frozenset(
    {
        "ONLINE_CASINO",
        "SLOTS",
        "LIVE_CASINO",
        "POKER",
        "BINGO",
        "LOTTERY",
        "SOCIAL_CASINO",
    }
)
BETTING_CATEGORIES = frozenset(
    {
        "SPORTSBOOK",
        "ESPORTS_BETTING",
        "FANTASY_SPORTS",
        "PREDICTION_PLATFORMS",
    }
)


def destination_compliance_block(offer: Offer) -> str | None:
    category = (offer.category or "").upper()
    if category in GAMBLING_CATEGORIES:
        return "COMPLIANCE_VERTICAL_FORBIDDEN"
    if category in BETTING_CATEGORIES and offer.access_policy == AccessPolicy.OPEN.value:
        return "COMPLIANCE_RESTRICTED_REQUIRED"
    return None


def assert_destination_compliance(offer: Offer) -> None:
    block = destination_compliance_block(offer)
    if block == "COMPLIANCE_VERTICAL_FORBIDDEN":
        raise AppError(
            block,
            "Страницы gambling-вертикали публиковать нельзя.",
            403,
        )
    if block == "COMPLIANCE_RESTRICTED_REQUIRED":
        raise AppError(
            block,
            "Ставки можно продвигать только после одобрения или по приглашению.",
            403,
        )
