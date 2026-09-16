from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.modules.partners.models import PartnerProfile
from app.modules.partners.privacy import (
    PARTNER_CONTACT_KEYS,
    looks_like_contact,
    partner_public_display_name,
    strip_partner_contact_fields,
)
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal
from tests.helpers import (
    create_partner_link,
    offer_payload,
    partner_with_access,
    register_business,
)


def test_partner_public_display_name_prefers_safe_nickname():
    assert (
        partner_public_display_name(
            partner_id=12,
            display_name="Мария",
            email="maria@example.com",
        )
        == "Мария"
    )


def test_partner_public_display_name_rejects_email_and_email_local_part():
    assert (
        partner_public_display_name(
            partner_id=44,
            display_name="hidden@example.com",
            email="hidden@example.com",
            first_name="",
            last_name="",
        )
        == "Партнёр #44"
    )
    assert (
        partner_public_display_name(
            partner_id=44,
            display_name="hidden",
            email="hidden@example.com",
            first_name="",
            last_name="",
        )
        == "Партнёр #44"
    )


def test_partner_public_display_name_uses_real_name_before_system_id():
    assert (
        partner_public_display_name(
            partner_id=9,
            display_name="hidden@example.com",
            email="hidden@example.com",
            first_name="Иван",
            last_name="Петров",
        )
        == "Иван Петров"
    )


def test_looks_like_contact_covers_messengers_and_phones():
    assert looks_like_contact("user@mail.com")
    assert looks_like_contact("@channel")
    assert looks_like_contact("t.me/refiq")
    assert looks_like_contact("+79991234567")
    assert looks_like_contact("https://instagram.com/user")
    assert not looks_like_contact("Мария")


def test_strip_partner_contact_fields_drops_private_keys():
    payload = strip_partner_contact_fields(
        {"name": "Мария", "email": "a@b.c", "telegram": "@x", "status": "approved"}
    )
    assert payload == {"name": "Мария", "status": "approved"}


def _walk_leaks(payload: Any, secrets: list[str], path: str = "$") -> list[str]:
    found: list[str] = []
    needles = [item.lower() for item in secrets if item]
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in PARTNER_CONTACT_KEYS:
                found.append(f"{path}.{key}")
            found.extend(_walk_leaks(value, secrets, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_walk_leaks(value, secrets, f"{path}[{index}]"))
    elif isinstance(payload, str):
        text = payload.lower()
        for needle in needles:
            if needle in text:
                found.append(f"{path} contains {needle}")
    return found


async def _set_partner_profile(
    email: str,
    *,
    display_name: str | None,
    first_name: str | None = "Test",
    last_name: str | None = "User",
) -> int:
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email.lower()))).scalar_one()
        user.first_name = first_name
        user.last_name = last_name
        profile = (
            await session.execute(select(PartnerProfile).where(PartnerProfile.user_id == user.id))
        ).scalar_one()
        profile.display_name = display_name
        await session.commit()
        return profile.id


@pytest.mark.asyncio
async def test_business_cannot_read_partner_contacts_via_api(client: AsyncClient):
    partner_email = "secret-partner@example.com"
    partner_phone = "+79990001122"
    partner_telegram = "@secret_partner"
    partner_website = "https://partner-site.example.com"
    secrets = [partner_email, partner_phone, partner_telegram, partner_website, "secret_partner"]

    await register_business(client, "privacy-biz@example.com")
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Privacy Offer",
            access_policy="approval",
            status="active",
            product_url="https://privacy.example.com",
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert created.status_code == 200
    offer_id = created.json()["id"]

    partner = await partner_with_access(offer_id, partner_email, "Мария Канал")
    try:
        patched = await partner.patch(
            "/api/v1/me",
            json={
                "phone": partner_phone,
                "telegram": partner_telegram,
                "website": partner_website,
            },
        )
        assert patched.status_code == 200
        assert patched.json()["email"] == partner_email
        assert patched.json()["phone"] == partner_phone
        assert patched.json()["telegram"] == partner_telegram

        own_offer = await partner.get(f"/api/v1/partner/offers/{offer_id}")
        assert own_offer.status_code == 200
        assert own_offer.json()["partner_profile"]["email"] == partner_email

        blocked_partner_api = await client.get("/api/v1/partner/settings")
        assert blocked_partner_api.status_code == 403
        blocked_marketplace = await client.get("/api/v1/partner/offers/marketplace")
        assert blocked_marketplace.status_code == 403

        detail = await client.get(f"/api/v1/business/offers/{offer_id}")
        assert detail.status_code == 200
        pending = detail.json()["pending_applications"]
        assert len(pending) == 1
        access_id = pending[0]["id"]
        assert pending[0]["name"] == "Мария Канал"
        assert "email" not in pending[0]

        approve = await client.post(f"/api/v1/business/offers/{offer_id}/partners/{access_id}/approve")
        assert approve.status_code == 200

        link = await create_partner_link(partner, offer_id)
        approved_detail = await client.get(f"/api/v1/business/offers/{offer_id}")
        assert approved_detail.status_code == 200
        partners = approved_detail.json()["partners"]
        assert partners[0]["status"] == "approved"
        assert "email" not in partners[0]
        assert partners[0]["name"] == "Мария Канал"

        link_detail = await client.get(f"/api/v1/business/offers/{offer_id}/links/{link['id']}")
        assert link_detail.status_code == 200
        assert link_detail.json().get("partner_name") == "Мария Канал"

        listed = await client.get("/api/v1/business/partners")
        assert listed.status_code == 200
        assert listed.json()["items"]
        assert "email" not in listed.json()["items"][0]
        assert listed.json()["items"][0]["display_name"] == "Мария Канал"

        export = await client.get("/api/v1/business/partners/export")
        assert export.status_code != 200
        csv_export = await client.get("/api/v1/business/partners.csv")
        assert csv_export.status_code != 200

        payloads = [
            listed.json(),
            approved_detail.json(),
            (await client.get(f"/api/v1/business/partners/{partners[0]['partner_id']}")).json(),
            (await client.get("/api/v1/business/dashboard?days=7")).json(),
            (await client.get("/api/v1/business/conversions")).json(),
            (await client.get("/api/v1/business/campaigns")).json(),
            (await client.get("/api/v1/business/payouts")).json(),
            (await client.get("/api/v1/notifications")).json(),
            link_detail.json(),
        ]
        leaks = []
        for payload in payloads:
            leaks.extend(_walk_leaks(payload, secrets))
        assert leaks == []
    finally:
        await partner.aclose()


@pytest.mark.asyncio
async def test_business_does_not_see_email_even_when_display_name_is_email(client: AsyncClient):
    partner_email = "alias-partner@example.com"
    await register_business(client, "alias-biz@example.com")
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Alias Offer",
            access_policy="open",
            status="active",
            product_url="https://alias.example.com",
            allowed_traffic=["seo", "telegram"],
        ),
    )
    offer_id = created.json()["id"]
    partner = await partner_with_access(offer_id, partner_email, partner_email)
    try:
        partner_id = await _set_partner_profile(
            partner_email,
            display_name=partner_email,
            first_name=None,
            last_name=None,
        )
        invite = await client.post(
            f"/api/v1/business/offers/{offer_id}/invite",
            json={"email": partner_email},
        )
        assert invite.status_code == 200
        assert "email" not in invite.json()

        detail = await client.get(f"/api/v1/business/offers/{offer_id}")
        assert detail.status_code == 200
        row = detail.json()["partners"][0]
        assert row["name"] == f"Партнёр #{partner_id}"
        assert partner_email not in str(detail.json())

        listed = await client.get("/api/v1/business/partners")
        assert listed.json()["items"][0]["display_name"] == f"Партнёр #{partner_id}"
        assert partner_email not in str(listed.json())
    finally:
        await partner.aclose()
