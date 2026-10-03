from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.audit.outbox.models import AuditOutboxEvent
from app.modules.auth.email_confirmation import INVALID_TOKEN_MESSAGE
from app.modules.auth.models import EmailConfirmationToken
from app.modules.auth.password_reset import generate_reset_token, hash_reset_token
from app.modules.users.models import User
from tests.conftest import TestingSessionLocal
from tests.mail_outbox import assert_no_plaintext, decrypt_mail, mail_events


def _token_from_url(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("token") or []
    assert values, "token missing in confirmation url"
    return values[0]


async def _load_user(email: str) -> User:
    async with TestingSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.expunge(user)
        return user


async def _load_tokens():
    async with TestingSessionLocal() as session:
        return list((await session.execute(select(EmailConfirmationToken))).scalars().all())


async def _confirmation(email: str) -> tuple[User, dict, str]:
    user = await _load_user(email)
    events = await mail_events(user.id, "ACCOUNT_CONFIRMATION")
    assert len(events) == 1
    payload = events[0].payload
    sensitive = decrypt_mail(payload)
    url = sensitive["variables"]["confirmUrl"]
    return user, payload, _token_from_url(url)


@pytest.mark.asyncio
async def test_register_creates_user_token_and_encrypted_mail_event(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "confirm-me@example.com",
        "password": "testpass123",
        "first_name": "Confirm",
        "last_name": "Me",
    })
    assert response.status_code == 200
    assert "refiq_session" not in response.cookies
    user, payload, token = await _confirmation("confirm-me@example.com")
    assert user.status == "new"
    assert user.email_verified_at is None
    assert payload["templateCode"] == "ACCOUNT_CONFIRMATION"
    assert payload["templateVersion"] == 1
    assert payload["eventType"] == "MAIL_SEND_REQUESTED"
    assert payload["idempotencyKey"].startswith("account-confirmation:")
    rows = await _load_tokens()
    assert len(rows) == 1
    assert payload["idempotencyKey"] == f"account-confirmation:{rows[0].id}"
    assert token not in rows[0].token_hash
    assert rows[0].token_hash == hash_reset_token(token)
    events = await mail_events(user.id, "ACCOUNT_CONFIRMATION")
    assert events[0].topic == "mail-events"
    assert events[0].event_id == payload["eventId"]
    assert events[0].partition_key == str(user.id)
    assert events[0].published_at is None
    sensitive = decrypt_mail(payload)
    assert sensitive["recipient"]["email"] == "confirm-me@example.com"
    assert sensitive["variables"]["ttlHours"] == 24
    assert token in sensitive["variables"]["confirmUrl"]
    assert_no_plaintext(payload, "confirm-me@example.com", token, sensitive["variables"]["confirmUrl"])


@pytest.mark.asyncio
async def test_login_rejected_until_confirmed(client: AsyncClient):
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
async def test_confirm_email_activates_account_without_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "activate@example.com",
        "password": "testpass123",
        "first_name": "Act",
        "last_name": "Ive",
    })
    _user, _payload, token = await _confirmation("activate@example.com")
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
async def test_confirm_email_login_creates_session(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "autologin@example.com",
        "password": "testpass123",
        "first_name": "Auto",
        "last_name": "Login",
    })
    _user, _payload, token = await _confirmation("autologin@example.com")
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


@pytest.mark.asyncio
async def test_register_commits_user_and_mail_event_together(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "atomic-confirm@example.com",
        "password": "testpass123",
        "first_name": "Atom",
        "last_name": "Ic",
    })
    assert response.status_code == 200
    user = await _load_user("atomic-confirm@example.com")
    async with TestingSessionLocal() as session:
        stored_user = await session.get(User, user.id)
        outbox = (
            await session.execute(
                select(AuditOutboxEvent).where(AuditOutboxEvent.aggregate_id == str(user.id))
            )
        ).scalar_one()
    assert stored_user is not None
    assert outbox.event_type == "MAIL_SEND_REQUESTED"
    assert outbox.payload["eventId"] == outbox.event_id
