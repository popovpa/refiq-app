import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversions.models import Conversion
from app.modules.links.models import Click
from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


async def _setup_click(client: AsyncClient, db: AsyncSession, email: str) -> str:
    await register_business(client, email)
    offer = await client.post("/api/v1/business/offers", json=offer_payload(
        name="CRM Pro",
        product_url="https://crmpro.example.com/pricing",
        status="active",
        access_policy="open",
        visibility="public",
        commission_type="percent",
        commission_value=10,
        allowed_traffic=["seo", "telegram"],
    ))
    assert offer.status_code == 200
    offer_id = offer.json()["id"]

    partner = await partner_with_access(offer_id, f"{email}.partner")
    created = await create_partner_link(partner, offer_id)
    short_code = created["short_code"]

    redirected = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert redirected.status_code == 302
    db.expire_all()
    result = await db.execute(select(Click).order_by(Click.id.desc()))
    click = result.scalars().first()
    assert click is not None
    return click.rqcid


@pytest.mark.asyncio
async def test_postback_requires_bearer_token(client: AsyncClient):
    missing = await client.post("/postback", json={"rqcid": "abcdefghijkl"})
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    assert missing.json()["error"]["message"] == "Invalid or missing token"
    _assert_no_sensitive_details(missing.json()["error"]["message"])

    bad_scheme = await client.post(
        "/postback",
        json={"rqcid": "abcdefghijkl"},
        headers={"Authorization": "Basic abc"},
    )
    assert bad_scheme.status_code == 401
    assert bad_scheme.json()["error"]["message"] == "Invalid or missing token"
    _assert_no_sensitive_details(bad_scheme.json()["error"]["message"])

    unknown = await client.post(
        "/postback",
        json={"rqcid": "abcdefghijkl"},
        headers={"Authorization": "Bearer rqpb_not-a-real-token"},
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"]["message"] == "Invalid or missing token"
    _assert_no_sensitive_details(unknown.json()["error"]["message"])


@pytest.mark.asyncio
async def test_create_postback_token_shown_once(client: AsyncClient):
    await register_business(client, "postback-token@example.com")

    empty = await client.get("/api/v1/business/postback/credential")
    assert empty.status_code == 200
    assert empty.json()["configured"] is False
    assert empty.json()["integration_status"] == "not_configured"
    assert "token" not in empty.json() or empty.json().get("token") in (None, "")

    created = await client.post("/api/v1/business/postback/credential")
    assert created.status_code == 200
    token = created.json()["token"]
    suffix = created.json()["token_suffix"]
    assert token.startswith("rqpb_")
    assert token.endswith(suffix)
    assert len(suffix) == 4

    status = await client.get("/api/v1/business/postback/credential")
    data = status.json()
    assert data["configured"] is True
    assert data["token_suffix"] == suffix
    assert data["token_status"] == "active"
    assert data["integration_status"] == "awaiting_first_request"
    assert "token" not in data or data.get("token") in (None, "")
    assert token not in str(data)

    again = await client.post("/api/v1/business/postback/credential")
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_postback_accepts_valid_token_and_rqcid(client: AsyncClient, db: AsyncSession):
    rqcid = await _setup_click(client, db, "postback-ok@example.com")
    created = await client.post("/api/v1/business/postback/credential")
    token = created.json()["token"]

    accepted = await client.post(
        "/postback",
        json={"rqcid": rqcid, "amount": 1000, "currency": "RUB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    db.expire_all()
    conversion = (await db.execute(select(Conversion).where(Conversion.click_id == rqcid))).scalar_one()
    assert conversion.status == "pending"
    assert float(conversion.amount) == 1000
    assert float(conversion.commission_amount) == 100

    status = await client.get("/api/v1/business/postback/credential")
    assert status.json()["integration_status"] == "connected"
    assert status.json()["last_success_at"] is not None


@pytest.mark.asyncio
async def test_postback_rotate_invalidates_old_token(client: AsyncClient, db: AsyncSession):
    rqcid = await _setup_click(client, db, "postback-rotate@example.com")
    first = await client.post("/api/v1/business/postback/credential")
    old_token = first.json()["token"]

    rotated = await client.post("/api/v1/business/postback/credential/rotate")
    new_token = rotated.json()["token"]
    assert new_token != old_token
    assert new_token.startswith("rqpb_")

    rejected = await client.post(
        "/postback",
        json={"rqcid": rqcid},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert rejected.status_code == 401

    accepted = await client.post(
        "/postback",
        json={"rqcid": rqcid},
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_postback_unknown_rqcid_is_generic(client: AsyncClient):
    await register_business(client, "postback-bad-click@example.com")
    created = await client.post("/api/v1/business/postback/credential")
    token = created.json()["token"]

    response = await client.post(
        "/postback",
        json={"rqcid": "zzzzzzzzzzzz"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_POSTBACK"
    assert response.json()["error"]["message"] == "Invalid parameters or token"
    assert "zzzzzzzzzzzz" not in response.json()["error"]["message"]
    _assert_no_sensitive_details(response.json()["error"]["message"])


@pytest.mark.asyncio
async def test_postback_validation_errors_are_generic(client: AsyncClient, db: AsyncSession):
    rqcid = await _setup_click(client, db, "postback-owner@example.com")
    owner_token = (await client.post("/api/v1/business/postback/credential")).json()["token"]

    await register_business(
        client,
        "postback-other@example.com",
        name="Other Biz",
        website="https://other.example.com",
    )
    other_token = (await client.post("/api/v1/business/postback/credential")).json()["token"]

    mismatched = await client.post(
        "/postback",
        json={"rqcid": rqcid, "amount": 11, "currency": "RUB"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert mismatched.status_code == 400
    assert mismatched.json()["error"]["message"] == "Invalid parameters or token"
    _assert_no_sensitive_details(mismatched.json()["error"]["message"])
    assert rqcid not in mismatched.json()["error"]["message"]

    bad_rqcid = await client.post(
        "/postback",
        json={"rqcid": "not-a-click-id", "amount": 11, "currency": "RUB"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert bad_rqcid.status_code == 400
    assert bad_rqcid.json()["error"]["message"] == "Invalid parameters or token"
    _assert_no_sensitive_details(bad_rqcid.json()["error"]["message"])


def _assert_no_sensitive_details(message: str) -> None:
    lowered = message.lower()
    for needle in ("business", "partner", "offer", "click", "rqcid", "email"):
        assert needle not in lowered
