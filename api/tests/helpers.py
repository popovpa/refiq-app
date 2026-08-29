from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.users.models import User
from tests.conftest import TestingSessionLocal


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
