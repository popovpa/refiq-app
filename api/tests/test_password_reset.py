import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import verify_password
from app.modules.auth.models import PasswordResetToken
from app.modules.auth.password_reset import (
    GENERIC_OK,
    INVALID_TOKEN_MESSAGE,
    RATE_LIMIT_MAX,
    generate_reset_token,
    hash_reset_token,
)
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal
from tests.helpers import register_user
from tests.mail_outbox import assert_no_plaintext, decrypt_mail, mail_events

OK_MESSAGE = GENERIC_OK["message"]


def _token_from_url(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("token") or []
    assert values, "token missing in reset url"
    return values[0]


async def _load_tokens():
    async with TestingSessionLocal() as session:
        result = await session.execute(select(PasswordResetToken))
        return list(result.scalars().all())


async def _load_user(email: str) -> User:
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.expunge(user)
        return user


async def _reset_token(email: str) -> tuple[dict, str]:
    user = await _load_user(email)
    events = await mail_events(user.id, "PASSWORD_RESET")
    assert events, "password reset mail event was not created"
    payload = events[-1].payload
    sensitive = decrypt_mail(payload)
    return payload, _token_from_url(sensitive["variables"]["resetUrl"])


@pytest.mark.asyncio
async def test_forgot_password_known_and_unknown_email_match(client: AsyncClient):
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
    user = await _load_user("reset-known@example.com")
    events = await mail_events(user.id, "PASSWORD_RESET")
    assert len(events) == 1
    payload = events[0].payload
    sensitive = decrypt_mail(payload)
    assert sensitive["recipient"]["email"] == "reset-known@example.com"
    assert sensitive["variables"]["ttlMinutes"] == 30
    assert_no_plaintext(
        payload,
        "reset-known@example.com",
        sensitive["variables"]["resetUrl"],
        _token_from_url(sensitive["variables"]["resetUrl"]),
    )
    assert payload["templateCode"] == "PASSWORD_RESET"
    assert events[0].topic == "mail-events"
    assert events[0].event_id == payload["eventId"]


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_does_not_create_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == OK_MESSAGE
    assert await _load_tokens() == []


@pytest.mark.asyncio
async def test_reset_token_hashed_with_expiration(client: AsyncClient):
    await register_user(client, "hashed@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "hashed@example.com"})
    payload, token = await _reset_token("hashed@example.com")
    rows = await _load_tokens()
    assert len(rows) == 1
    row = rows[0]
    assert token not in row.token_hash
    assert row.token_hash == hash_reset_token(token)
    assert len(row.token_hash) == 64
    assert payload["idempotencyKey"] == f"password-reset:{row.id}"
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    delta = expires - datetime.now(timezone.utc)
    assert timedelta(minutes=29) <= delta <= timedelta(minutes=31)
    sensitive = decrypt_mail(payload)
    assert_no_plaintext(payload, "hashed@example.com", token, sensitive["variables"]["resetUrl"])


@pytest.mark.asyncio
async def test_valid_token_changes_password_and_cannot_be_reused(client: AsyncClient):
    await register_user(client, "reuse@example.com", password="oldpass123")
    me = await client.get("/api/v1/me")
    assert me.status_code == 200

    await client.post("/api/v1/auth/forgot-password", json={"email": "reuse@example.com"})
    _payload, token = await _reset_token("reuse@example.com")

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
async def test_reset_password_validates_existing_policy(client: AsyncClient):
    await register_user(client, "policy@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "policy@example.com"})
    _payload, token = await _reset_token("policy@example.com")
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
async def test_forgot_password_rate_limit_is_preserved(client: AsyncClient):
    for _ in range(RATE_LIMIT_MAX):
        allowed = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "limited@example.com"},
        )
        assert allowed.status_code == 200
        assert allowed.json() == GENERIC_OK
    blocked = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "limited@example.com"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert await _load_tokens() == []


@pytest.mark.asyncio
async def test_new_reset_request_invalidates_previous_token(client: AsyncClient):
    await register_user(client, "rotate@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "rotate@example.com"})
    _first_payload, first = await _reset_token("rotate@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "rotate@example.com"})
    _second_payload, second = await _reset_token("rotate@example.com")
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
async def test_concurrent_reset_uses_token_only_once(client: AsyncClient):
    await register_user(client, "race@example.com", password="oldpass123")
    await client.post("/api/v1/auth/forgot-password", json={"email": "race@example.com"})
    _payload, token = await _reset_token("race@example.com")
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
