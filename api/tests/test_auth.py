import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_session_required(client: AsyncClient):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "письма" in data["message"] or "письмо" in data["message"]
    assert "refiq_session" not in response.cookies
    assert "user" not in data


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "testpass123",
        "first_name": "Dup",
        "last_name": "User",
    })
    response = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "testpass123",
        "first_name": "Dup",
        "last_name": "User",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    from tests.helpers import register_user

    await register_user(client, "login@example.com")
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "testpass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "badpw@example.com",
        "password": "testpass123",
        "first_name": "Bad",
        "last_name": "Pw",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "badpw@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_switch_role_roundtrip_keeps_session(client: AsyncClient):
    from tests.helpers import become_business, become_partner, register_user

    register = await register_user(client, "both-roles@example.com", first_name="Both", last_name="Roles")
    assert register.json()["active_role"] is None

    business_role = await become_business(client, work_email="both-roles@example.com")
    assert business_role.status_code == 200
    assert business_role.json()["active_role"] == "business"
    assert business_role.json()["active_business_id"] is not None

    partner_role = await become_partner(client, "Both Roles")
    assert partner_role.status_code == 200
    assert partner_role.json()["active_role"] == "business"

    to_partner = await client.post("/api/v1/me/context", json={"role": "partner"})
    assert to_partner.status_code == 200
    assert to_partner.json()["active_role"] == "partner"
    assert to_partner.json()["active_business_id"] is None

    to_business = await client.post("/api/v1/me/context", json={"role": "business"})
    assert to_business.status_code == 200
    payload = to_business.json()
    assert payload["active_role"] == "business"
    assert payload["active_business_id"] is not None
    assert isinstance(payload["active_business_id"], str)

    session = await client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["active_role"] == "business"
    assert session.json()["user"]["email"] == "both-roles@example.com"
    assert session.json()["business_name"] == "Acme"
    assert session.json()["partner_name"] == "Both Roles"


@pytest.mark.asyncio
async def test_profile_update_and_password_change(client: AsyncClient):
    from tests.helpers import register_user

    await register_user(client, "profile@example.com", first_name="Anna", last_name="Ivanova")

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "profile@example.com"
    assert me.json()["created_at"] is not None

    updated = await client.patch("/api/v1/me", json={
        "phone": "+79990001122",
        "city": "Москва",
        "telegram": "@anna",
        "country": "RU",
        "language": "ru",
    })
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+79990001122"
    assert updated.json()["city"] == "Москва"
    assert updated.json()["telegram"] == "@anna"

    bad_password = await client.post("/api/v1/me/password", json={
        "current_password": "wrong",
        "new_password": "Newpass123!",
    })
    assert bad_password.status_code == 400

    ok_password = await client.post("/api/v1/me/password", json={
        "current_password": "testpass123",
        "new_password": "Newpass123!",
        "logout_other_sessions": False,
    })
    assert ok_password.status_code == 200

    login = await client.post("/api/v1/auth/login", json={
        "email": "profile@example.com",
        "password": "Newpass123!",
    })
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_register_validation(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "invalid",
        "password": "short",
        "first_name": "",
        "last_name": "",
    })
    assert response.status_code == 422
