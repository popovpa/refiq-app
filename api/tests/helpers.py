from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.users.models import User
from tests.conftest import TestingSessionLocal


OFFER_REQUIRED = {
    "description": "Партнёрское предложение",
    "category": "SaaS",
    "geo": "RU",
    "conversion_type": "sale",
    "commission_type": "percent",
    "commission_value": 10,
    "attribution_window_days": 30,
    "hold_period_days": 0,
    "access_policy": "open",
    "allowed_traffic": ["EMAIL"],
}


def offer_payload(**overrides):
    payload = {
        "name": "Test offer",
        "status": "draft",
        **OFFER_REQUIRED,
    }
    payload.update(overrides)
    return payload


BUSINESS_PAYLOAD = {
    "name": "Acme",
    "website": "https://acme.example.com",
    "country": "RU",
    "category": "SaaS",
    "work_email": "work@acme.example.com",
    "phone": "+79991112233",
    "description": "Test company",
}


async def register_user(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
    first_name: str = "Test",
    last_name: str = "User",
):
    response = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
    })
    assert response.status_code == 200, response.text
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email.lower()))).scalar_one()
        user.status = "active"
        user.email_verified_at = datetime.now(timezone.utc)
        await session.commit()
    login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login.status_code == 200, login.text
    return login


async def become_business(client: AsyncClient, **overrides):
    payload = {**BUSINESS_PAYLOAD, **overrides}
    response = await client.post("/api/v1/me/roles/business", json=payload)
    assert response.status_code == 200, response.text
    return response


async def become_partner(client: AsyncClient, display_name: str | None = None):
    body = {"display_name": display_name} if display_name else {}
    response = await client.post("/api/v1/me/roles/partner", json=body)
    assert response.status_code == 200, response.text
    return response


async def register_business(client: AsyncClient, email: str, **overrides):
    await register_user(client, email)
    return await become_business(client, work_email=email, **overrides)


async def external_partner(email: str, display_name: str = "Partner") -> AsyncClient:
    from httpx import ASGITransport
    from tests.conftest import fastapi_app

    partner = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")
    await register_user(partner, email)
    await become_partner(partner, display_name)
    switch = await partner.post("/api/v1/me/context", json={"role": "partner"})
    assert switch.status_code == 200, switch.text
    return partner


async def partner_with_access(offer_id: str | int, email: str, display_name: str = "Partner") -> AsyncClient:
    partner = await external_partner(email, display_name)
    join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200, join.text
    return partner


async def create_partner_link(
    partner: AsyncClient,
    offer_id: str | int,
    *,
    name: str = "Telegram",
    traffic_source: str = "telegram",
    destination_url: str | None = None,
) -> dict:
    payload = {
        "offer_id": offer_id,
        "name": name,
        "traffic_source": traffic_source,
    }
    if destination_url:
        payload["destination_url"] = destination_url
    created = await partner.post("/api/v1/partner/links", json=payload)
    assert created.status_code == 200, created.text
    return created.json()
