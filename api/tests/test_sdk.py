import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sdk.models import SdkScript
from app.modules.sdk.script_id import SCRIPT_ID_PATTERN, generate_script_id, is_valid_script_id
from tests.helpers import register_business

SCRIPT_ID_RE = re.compile(SCRIPT_ID_PATTERN)


def test_generate_script_id_is_five_lowercase_alphanumeric():
    value = generate_script_id()
    assert is_valid_script_id(value)
    assert SCRIPT_ID_RE.fullmatch(value)
    assert value == value.lower()
    assert len(value) == 5


@pytest.mark.asyncio
async def test_create_sdk_script_id_and_snippet_identity(client: AsyncClient, db: AsyncSession):
    await register_business(client, "sdk-token@example.com")

    empty = await client.get("/api/v1/business/sdk/credential")
    assert empty.status_code == 200
    assert empty.json()["configured"] is False
    assert empty.json()["integration_status"] == "not_configured"
    assert empty.json().get("script_id") in (None, "")

    created = await client.post("/api/v1/business/sdk/credential")
    assert created.status_code == 200
    script_id = created.json()["script_id"]
    assert SCRIPT_ID_RE.fullmatch(script_id)
    assert script_id == script_id.lower()

    status = await client.get("/api/v1/business/sdk/credential")
    data = status.json()
    assert data["configured"] is True
    assert data["script_id"] == script_id
    assert data["integration_status"] == "awaiting_first_request"

    dashboard = await client.get("/api/v1/business/dashboard?days=7")
    assert dashboard.status_code == 200
    assert dashboard.json()["integrations"]["sdk"] == "awaiting_first_request"

    db.expire_all()
    stored = (await db.execute(select(SdkScript).where(SdkScript.script_id == script_id))).scalar_one()
    assert stored.script_id == script_id

    again = await client.post("/api/v1/business/sdk/credential")
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_sdk_script_ids_are_unique_across_businesses(client: AsyncClient):
    await register_business(client, "sdk-one@example.com", name="One Biz", website="https://one.example.com")
    first = await client.post("/api/v1/business/sdk/credential")
    assert first.status_code == 200
    first_id = first.json()["script_id"]

    await register_business(client, "sdk-two@example.com", name="Two Biz", website="https://two.example.com")
    second = await client.post("/api/v1/business/sdk/credential")
    assert second.status_code == 200
    second_id = second.json()["script_id"]

    assert SCRIPT_ID_RE.fullmatch(first_id)
    assert SCRIPT_ID_RE.fullmatch(second_id)
    assert first_id != second_id


@pytest.mark.asyncio
async def test_sdk_clickstream_event_marks_connected(client: AsyncClient):
    await register_business(client, "sdk-event@example.com")
    script_id = (await client.post("/api/v1/business/sdk/credential")).json()["script_id"]

    accepted = await client.post(
        "/event",
        content='{"event":"page_view","script_id":"%s","url":"http://localhost:5500/"}' % script_id,
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )
    assert accepted.status_code == 204

    status = await client.get("/api/v1/business/sdk/credential")
    data = status.json()
    assert data["integration_status"] == "connected"
    assert data["last_success_at"] is not None

    unknown = await client.post(
        "/event",
        content='{"event":"page_view","script_id":"zzzzz"}',
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )
    assert unknown.status_code == 204


@pytest.mark.asyncio
async def test_sdk_batch_events_and_site_id_alias(client: AsyncClient):
    await register_business(client, "sdk-batch@example.com")
    script_id = (await client.post("/api/v1/business/sdk/credential")).json()["script_id"]

    accepted = await client.post(
        "/events",
        content='[{"event":"page_view","site_id":"%s"},{"event":"click","script_id":"%s","rqcid":"abc123xyz789"}]'
        % (script_id, script_id),
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )
    assert accepted.status_code == 204
    status = await client.get("/api/v1/business/sdk/credential")
    assert status.json()["integration_status"] == "connected"
    assert status.json()["sites_count"] == 1
    assert status.json()["connected_sites"] == 1

