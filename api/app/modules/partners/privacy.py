from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.partners.models import PartnerProfile
from app.modules.users.models import User

PARTNER_CONTACT_KEYS = frozenset(
    {
        "email",
        "phone",
        "telegram",
        "whatsapp",
        "whats_app",
        "website",
        "contact",
        "contacts",
        "social",
        "socials",
        "social_url",
        "instagram",
        "vk",
        "facebook",
        "linkedin",
        "messenger",
        "messengers",
        "personal_site",
        "contact_url",
        "t_me",
        "wa",
        "wa_me",
    }
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[\d+\-\s().]{8,}$")
_HANDLE_PREFIXES = (
    "http://",
    "https://",
    "t.me/",
    "telegram.me/",
    "wa.me/",
    "www.",
)


def looks_like_email(value: str | None) -> bool:
    text = (value or "").strip()
    return bool(text) and bool(_EMAIL_RE.match(text))


def looks_like_contact(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if looks_like_email(text) or "@" in text:
        return True
    lowered = text.lower()
    if lowered.startswith(_HANDLE_PREFIXES) or lowered.startswith("@"):
        return True
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 10 and _PHONE_RE.match(text):
        return True
    return False


def _is_email_derived(name: str, email: str | None) -> bool:
    if not email:
        return False
    candidate = name.strip().lower()
    full = email.strip().lower()
    local = full.split("@", 1)[0]
    return candidate == full or candidate == local


def partner_public_display_name(
    *,
    partner_id: int | None = None,
    display_name: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> str:
    candidates = [
        (display_name or "").strip(),
        f"{first_name or ''} {last_name or ''}".strip(),
    ]
    for name in candidates:
        if not name or looks_like_contact(name) or _is_email_derived(name, email):
            continue
        return name
    if partner_id:
        return f"Партнёр #{partner_id}"
    return "Партнёр"


def partner_public_display_name_from(
    profile: PartnerProfile | None,
    user: User | None = None,
) -> str:
    if profile is None:
        return "Партнёр"
    return partner_public_display_name(
        partner_id=profile.id,
        display_name=profile.display_name,
        email=user.email if user else None,
        first_name=user.first_name if user else None,
        last_name=user.last_name if user else None,
    )


def strip_partner_contact_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key.lower() not in PARTNER_CONTACT_KEYS}


def scrub_partner_contacts(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_partner_contacts(item)
            for key, item in value.items()
            if key.lower() not in PARTNER_CONTACT_KEYS
        }
    if isinstance(value, list):
        return [scrub_partner_contacts(item) for item in value]
    return value


async def load_partner_public_name(db: AsyncSession, partner_id: int | None) -> str | None:
    if not partner_id:
        return None
    row = (
        await db.execute(
            select(PartnerProfile, User)
            .join(User, PartnerProfile.user_id == User.id)
            .where(PartnerProfile.id == partner_id)
        )
    ).first()
    if not row:
        return f"Партнёр #{partner_id}"
    return partner_public_display_name_from(row.PartnerProfile, row.User)
