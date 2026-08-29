import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import verify_password
from app.modules.auth.models import PasswordResetToken
from app.modules.auth.password_reset import (
    GENERIC_OK,
    INVALID_TOKEN_MESSAGE,
    generate_reset_token,
    hash_reset_token,
)
from app.modules.email.deps import set_email_provider
from app.modules.email.dto import EmailMessage
from app.modules.email.errors import EmailSendError
from app.modules.email.templates.password_reset import render_password_reset
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal
from tests.helpers import register_user

OK_MESSAGE = GENERIC_OK["message"]


class RecordingEmailProvider:
    def __init__(self):
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


class FailingEmailProvider:
    async def send(self, message: EmailMessage) -> None:
        raise EmailSendError("Failed to send email")


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


def _reset_url(message: EmailMessage) -> str:
    for line in message.text.splitlines():
        if "/reset-password?token=" in line:
            return line.strip()
    raise AssertionError("reset URL not found in email")


def _reset_messages(emails) -> list[EmailMessage]:
    return [message for message in emails.messages if "/reset-password?token=" in message.text]


def _latest_reset_url(emails) -> str:
    messages = _reset_messages(emails)
    assert messages, "reset URL not found in email"
    return _reset_url(messages[-1])


async def _load_tokens():
    async with TestingSessionLocal() as session:
        result = await session.execute(select(PasswordResetToken))
        return list(result.scalars().all())


async def _load_user(email: str) -> User:
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.expunge(user)
        return user


@pytest.mark.asyncio
async def test_forgot_password_known_and_unknown_email_match(client: AsyncClient, emails):
    await register_user(client, "reset-known@example.com")
    existing = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "Reset-Known@example.com"},
    )
    missing = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json() == missing.json() == GENERIC_OK
    reset_mail = _reset_messages(emails)
    assert len(reset_mail) == 1
    assert reset_mail[0].to == "reset-known@example.com"


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_does_not_create_token(client: AsyncClient, emails):
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == OK_MESSAGE
    assert emails.messages == []
    assert await _load_tokens() == []


@pytest.mark.asyncio
async def test_reset_token_hashed_with_expiration(client: AsyncClient, emails):
    await register_user(client, "hashed@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "hashed@example.com"})
    token = _token_from_url(_latest_reset_url(emails))
    rows = await _load_tokens()
    assert len(rows) == 1
    row = rows[0]
    assert token not in row.token_hash
    assert row.token_hash == hash_reset_token(token)
    assert len(row.token_hash) == 64
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    delta = expires - datetime.now(timezone.utc)
    assert timedelta(minutes=29) <= delta <= timedelta(minutes=31)


@pytest.mark.asyncio
async def test_valid_token_changes_password_and_cannot_be_reused(client: AsyncClient, emails):
    await register_user(client, "reuse@example.com", password="oldpass123")
    me = await client.get("/api/v1/me")
    assert me.status_code == 200

    await client.post("/api/v1/auth/forgot-password", json={"email": "reuse@example.com"})
    token = _token_from_url(_latest_reset_url(emails))

    ok = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Newpass123!"},
    )
    assert ok.status_code == 200
    assert ok.json()["message"] == "Пароль успешно изменён"

    me_after = await client.get("/api/v1/me")
    assert me_after.status_code == 401

    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Anotherpass1"},
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["message"] == INVALID_TOKEN_MESSAGE

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reuse@example.com", "password": "oldpass123"},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reuse@example.com", "password": "Newpass123!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_expired_and_invalid_tokens_are_rejected(client: AsyncClient):
    await register_user(client, "expired@example.com")
    user = await _load_user("expired@example.com")
    token = generate_reset_token()
    async with TestingSessionLocal() as session:
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_reset_token(token),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Newpass123!"},
    )
    unknown = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": generate_reset_token(), "password": "Newpass123!"},
    )
    assert expired.status_code == 400
    assert unknown.status_code == 400
    assert expired.json()["error"]["message"] == INVALID_TOKEN_MESSAGE
    assert unknown.json()["error"]["message"] == INVALID_TOKEN_MESSAGE


@pytest.mark.asyncio
async def test_reset_password_validates_existing_policy(client: AsyncClient, emails):
    await register_user(client, "policy@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "policy@example.com"})
    token = _token_from_url(_latest_reset_url(emails))
    short = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "short"},
    )
    assert short.status_code == 422
    rows = await _load_tokens()
    assert rows[0].used_at is None
    user = await _load_user("policy@example.com")
    assert verify_password("testpass123", user.password_hash)


@pytest.mark.asyncio
async def test_email_provider_failure_is_logged_without_leaking(client: AsyncClient):
    await register_user(client, "failmail@example.com")
    set_email_provider(FailingEmailProvider())
    with patch("app.modules.auth.password_reset.logger.exception") as mocked:
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "failmail@example.com"},
        )
    assert response.status_code == 200
    assert response.json() == GENERIC_OK
    mocked.assert_called_once()
    assert mocked.call_args.args[0] == "password_reset_email_failed"
    assert "email" not in mocked.call_args.kwargs
    assert "token" not in mocked.call_args.kwargs
    assert "reset_url" not in mocked.call_args.kwargs
    tokens = await _load_tokens()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_new_reset_request_invalidates_previous_token(client: AsyncClient, emails):
    await register_user(client, "rotate@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "rotate@example.com"})
    first = _token_from_url(_latest_reset_url(emails))
    await client.post("/api/v1/auth/forgot-password", json={"email": "rotate@example.com"})
    second = _token_from_url(_latest_reset_url(emails))
    assert first != second
    stale = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": first, "password": "Newpass123!"},
    )
    assert stale.status_code == 400
    fresh = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": second, "password": "Newpass123!"},
    )
    assert fresh.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_reset_uses_token_only_once(client: AsyncClient, emails):
    await register_user(client, "race@example.com", password="oldpass123")
    await client.post("/api/v1/auth/forgot-password", json={"email": "race@example.com"})
    token = _token_from_url(_latest_reset_url(emails))
    first, second = await asyncio.gather(
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "NewpassAAA1"},
        ),
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "NewpassBBB1"},
        ),
    )
    successes = [r for r in (first, second) if r.status_code == 200]
    failures = [r for r in (first, second) if r.status_code != 200]
    assert len(successes) == 1
    assert len(failures) == 1
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "race@example.com", "password": "NewpassAAA1"},
    )
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "race@example.com", "password": "NewpassBBB1"},
    )
    assert (login_a.status_code == 200) + (login_b.status_code == 200) == 1


def test_password_reset_email_matches_landing_style():
    url = "https://app.refiq.ru/reset-password?token=exampletoken"
    subject, text, html = render_password_reset(reset_url=url, ttl_minutes=30)
    assert "Восстановление пароля" in subject
    assert url in text
    assert "30 минут" in text
    assert "<script" not in html.lower()
    assert "#f2f5ef" in html
    assert "#3d6b50" in html
    assert "#27503a" in html
    assert "border-radius:14px" in html
    assert "border-radius:999px" in html
    assert url in html
