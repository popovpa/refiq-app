from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.auth.email_confirmation import INVALID_TOKEN_MESSAGE
from app.modules.auth.models import EmailConfirmationToken
from app.modules.auth.password_reset import generate_reset_token, hash_reset_token
from app.modules.email.deps import set_email_provider
from app.modules.email.dto import EmailMessage
from app.modules.email.templates.account_confirmation import render_account_confirmation
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal


class RecordingEmailProvider:
    def __init__(self):
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest.fixture
def emails():
    provider = RecordingEmailProvider()
    set_email_provider(provider)
    yield provider
    set_email_provider(None)


def _token_from_url(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("token") or []
    assert values, f"token missing in {url}"
    return values[0]


def _confirm_url(message: EmailMessage) -> str:
    for line in message.text.splitlines():
        if "/confirm-account?token=" in line:
            return line.strip()
    raise AssertionError("confirm URL not found in email")


async def _load_user(email: str) -> User:
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.expunge(user)
        return user


async def _load_tokens():
    async with TestingSessionLocal() as session:
        return list((await session.execute(select(EmailConfirmationToken))).scalars().all())


@pytest.mark.asyncio
async def test_register_creates_new_user_and_sends_email(client: AsyncClient, emails):
    response = await client.post("/api/v1/auth/register", json={
        "email": "confirm-me@example.com",
        "password": "testpass123",
        "first_name": "Confirm",
        "last_name": "Me",
    })
    assert response.status_code == 200
    assert "refiq_session" not in response.cookies
    user = await _load_user("confirm-me@example.com")
    assert user.status == "new"
    assert user.email_verified_at is None
    assert len(emails.messages) == 1
    assert emails.messages[0].to == "confirm-me@example.com"
    assert "Подтвердить аккаунт" in emails.messages[0].html
    token = _token_from_url(_confirm_url(emails.messages[0]))
    rows = await _load_tokens()
    assert len(rows) == 1
    assert token not in rows[0].token_hash
    assert rows[0].token_hash == hash_reset_token(token)


@pytest.mark.asyncio
async def test_login_rejected_until_confirmed(client: AsyncClient, emails):
    await client.post("/api/v1/auth/register", json={
        "email": "pending@example.com",
        "password": "testpass123",
        "first_name": "Pending",
        "last_name": "User",
    })
    blocked = await client.post("/api/v1/auth/login", json={
        "email": "pending@example.com",
        "password": "testpass123",
    })
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ACCOUNT_NOT_CONFIRMED"


@pytest.mark.asyncio
async def test_confirm_email_activates_account_without_login(client: AsyncClient, emails):
    await client.post("/api/v1/auth/register", json={
        "email": "activate@example.com",
        "password": "testpass123",
        "first_name": "Act",
        "last_name": "Ive",
    })
    token = _token_from_url(_confirm_url(emails.messages[0]))
    confirmed = await client.post("/api/v1/auth/confirm-email", json={"token": token})
    assert confirmed.status_code == 200
    assert confirmed.json()["message"] == "Аккаунт подтверждён"
    assert "refiq_session" not in confirmed.cookies
    user = await _load_user("activate@example.com")
    assert user.status == "active"
    assert user.email_verified_at is not None
    me = await client.get("/api/v1/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_confirm_email_login_creates_session(client: AsyncClient, emails):
    await client.post("/api/v1/auth/register", json={
        "email": "autologin@example.com",
        "password": "testpass123",
        "first_name": "Auto",
        "last_name": "Login",
    })
    token = _token_from_url(_confirm_url(emails.messages[0]))
    await client.post("/api/v1/auth/confirm-email", json={"token": token})
    entered = await client.post("/api/v1/auth/confirm-email/login", json={"token": token})
    assert entered.status_code == 200
    assert entered.json()["user"]["email"] == "autologin@example.com"
    assert entered.json()["user"]["status"] == "active"
    assert "refiq_session" in entered.cookies
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    reused = await client.post("/api/v1/auth/confirm-email/login", json={"token": token})
    assert reused.status_code == 400
    assert reused.json()["error"]["message"] == INVALID_TOKEN_MESSAGE


@pytest.mark.asyncio
async def test_confirm_email_invalid_and_expired_tokens(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "expired-confirm@example.com",
        "password": "testpass123",
        "first_name": "Exp",
        "last_name": "Ired",
    })
    user = await _load_user("expired-confirm@example.com")
    token = generate_reset_token()
    async with TestingSessionLocal() as session:
        session.add(
            EmailConfirmationToken(
                user_id=user.id,
                token_hash=hash_reset_token(token),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()
    expired = await client.post("/api/v1/auth/confirm-email", json={"token": token})
    unknown = await client.post("/api/v1/auth/confirm-email", json={"token": generate_reset_token()})
    assert expired.status_code == 400
    assert unknown.status_code == 400
    assert expired.json()["error"]["message"] == INVALID_TOKEN_MESSAGE


def test_confirmation_email_matches_landing_style():
    url = "https://app.refiq.ru/confirm-account?token=exampletoken"
    subject, text, html = render_account_confirmation(confirm_url=url, ttl_hours=24)
    assert "Подтвердите аккаунт" in subject
    assert "Подтвердить аккаунт" in text
    assert url in text
    assert url in html
    assert "<script" not in html.lower()
    assert "#f2f5ef" in html
    assert "#3d6b50" in html
    assert "#27503a" in html
    assert "border-radius:14px" in html
    assert "border-radius:999px" in html
