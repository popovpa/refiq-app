import pytest
from httpx import AsyncClient

from tests.helpers import become_business, become_partner, register_user


@pytest.mark.asyncio
async def test_register_has_no_roles(client: AsyncClient):
    response = await register_user(client, "new-user@example.com")
    data = response.json()
    assert data["user"]["roles"] == []
    assert data["active_role"] is None

    forbidden = await client.get("/api/v1/business/dashboard")
    assert forbidden.status_code == 403

    partner_forbidden = await client.get("/api/v1/partner/dashboard")
    assert partner_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_activate_partner_and_repeat_is_idempotent(client: AsyncClient):
    await register_user(client, "new-partner@example.com", first_name="Ann", last_name="Lee")
    first = await become_partner(client)
    assert first.json()["active_role"] == "partner"
    roles = [item["role"] for item in first.json()["user"]["roles"]]
    assert roles == ["partner"]

    dashboard = await client.get("/api/v1/partner/dashboard")
    assert dashboard.status_code == 200

    second = await become_partner(client)
    assert second.status_code == 200
    assert second.json()["active_role"] == "partner"


@pytest.mark.asyncio
async def test_activate_business_then_login_restores_workspace(client: AsyncClient):
    await register_user(client, "new-biz@example.com", first_name="Bob", last_name="Biz")
    activated = await become_business(client, work_email="new-biz@example.com")
    assert activated.json()["active_role"] == "business"
    assert activated.json()["active_business_id"] is not None

    dashboard = await client.get("/api/v1/business/dashboard")
    assert dashboard.status_code == 200

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={
        "email": "new-biz@example.com",
        "password": "testpass123",
    })
    assert login.status_code == 200
    assert login.json()["active_role"] == "business"
    assert login.json()["active_business_id"] is not None


@pytest.mark.asyncio
async def test_second_role_keeps_current_workspace(client: AsyncClient):
    await register_user(client, "second-role@example.com")
    await become_partner(client)
    added = await become_business(client, work_email="second-role@example.com")
    assert added.json()["active_role"] == "partner"
    roles = {item["role"] for item in added.json()["user"]["roles"]}
    assert roles == {"partner", "business"}

    switched = await client.post("/api/v1/me/context", json={"role": "business"})
    assert switched.status_code == 200
    assert switched.json()["active_role"] == "business"

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={
        "email": "second-role@example.com",
        "password": "testpass123",
    })
    assert login.json()["active_role"] == "business"


@pytest.mark.asyncio
async def test_business_requires_company_fields(client: AsyncClient):
    await register_user(client, "incomplete-biz@example.com")
    response = await client.post("/api/v1/me/roles/business", json={"name": "Acme"})
    assert response.status_code == 422
