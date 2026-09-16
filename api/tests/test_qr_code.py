from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings as app_settings
from app.main import app as fastapi_app
from app.modules.assets.service import get_asset_storage, set_asset_storage
from app.modules.qr.service import qr_object_key
from tests.helpers import become_partner, create_partner_link, offer_payload, partner_with_access, register_business, register_user

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class FailingStorage:
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        raise RuntimeError("object storage unavailable")

    async def get(self, key: str) -> bytes:
        raise FileNotFoundError(key)

    async def exists(self, key: str) -> bool:
        return False


async def _create_partner_link(client: AsyncClient) -> tuple[str, dict, AsyncClient]:
    await register_business(client, "qr-biz@example.com")
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="QR Offer",
            product_url="https://crmpro.example.com/pricing",
            conversion_type="sale",
            status="active",
            access_policy="open",
            visibility="public",
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert offer.status_code == 200
    offer_id = offer.json()["id"]
    partner = await partner_with_access(offer_id, "qr-partner@example.com", "QR Partner")
    created = await create_partner_link(partner, offer_id)
    return offer_id, created, partner


def _assert_png_response(response, *, attachment: bool, short_code: str | None = None) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    disposition = response.headers["content-disposition"]
    if attachment:
        assert disposition.startswith("attachment")
        assert short_code is not None
        assert f"{short_code}.png" in disposition
    else:
        assert disposition.startswith("inline")
    assert response.content.startswith(PNG_MAGIC)


@pytest.mark.asyncio
async def test_create_link_stores_qr_png_without_qr_fields(client: AsyncClient):
    _offer_id, data, _partner = await _create_partner_link(client)
    assert "qr_url" not in data
    assert "qr_path" not in data
    assert "qr_file_id" not in data
    assert "qr_object_key" not in data

    key = qr_object_key(data["short_code"])
    storage = get_asset_storage()
    assert await storage.exists(key)
    png = await storage.get(key)
    assert png.startswith(PNG_MAGIC)


@pytest.mark.asyncio
async def test_partner_can_view_and_download_qr(client: AsyncClient):
    _offer_id, data, partner = await _create_partner_link(client)
    link_id = data["id"]
    short_code = data["short_code"]

    viewed = await partner.get(f"/api/v1/partner/links/{link_id}/qr-code")
    _assert_png_response(viewed, attachment=False)

    downloaded = await partner.get(f"/api/v1/partner/links/{link_id}/qr-code/download")
    _assert_png_response(downloaded, attachment=True, short_code=short_code)


@pytest.mark.asyncio
async def test_qr_self_heals_when_object_is_missing(client: AsyncClient):
    _offer_id, data, partner = await _create_partner_link(client)
    key = qr_object_key(data["short_code"])
    path = Path(app_settings.ASSET_STORAGE_DIR) / key
    assert path.is_file()
    path.unlink()
    assert not path.exists()

    viewed = await partner.get(f"/api/v1/partner/links/{data['id']}/qr-code")
    _assert_png_response(viewed, attachment=False)
    assert path.is_file()


@pytest.mark.asyncio
async def test_create_link_succeeds_when_qr_storage_fails(client: AsyncClient):
    set_asset_storage(FailingStorage())
    _offer_id, data, _partner = await _create_partner_link(client)
    assert data["id"]
    assert data["url"].startswith("https://go.refiq.ru/")


@pytest.mark.asyncio
async def test_qr_requires_auth_and_ownership(client: AsyncClient):
    _offer_id, data, _partner = await _create_partner_link(client)
    link_id = data["id"]

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as anonymous:
        unauth = await anonymous.get(f"/api/v1/partner/links/{link_id}/qr-code")
    assert unauth.status_code == 401

    await register_user(client, "other-qr@example.com")
    await become_partner(client, "Other Partner")
    switch = await client.post("/api/v1/me/context", json={"role": "partner"})
    assert switch.status_code == 200
    forbidden = await client.get(f"/api/v1/partner/links/{link_id}/qr-code")
    assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_disable_link_does_not_delete_qr(client: AsyncClient):
    _offer_id, data, partner = await _create_partner_link(client)
    key = qr_object_key(data["short_code"])
    storage = get_asset_storage()
    before = await storage.get(key)

    disabled = await partner.patch(f"/api/v1/partner/links/{data['id']}", json={"status": "DISABLED"})
    assert disabled.status_code == 200
    assert await storage.exists(key)
    assert await storage.get(key) == before

    viewed = await partner.get(f"/api/v1/partner/links/{data['id']}/qr-code")
    _assert_png_response(viewed, attachment=False)


@pytest.mark.asyncio
async def test_destination_change_does_not_regenerate_qr(client: AsyncClient):
    offer_id, data, _partner = await _create_partner_link(client)
    key = qr_object_key(data["short_code"])
    storage = get_asset_storage()
    before = await storage.get(key)

    updated = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{data['id']}",
        json={"destination_url": "https://crmpro.example.com/new-page"},
    )
    assert updated.status_code == 200
    assert await storage.get(key) == before


@pytest.mark.asyncio
async def test_business_can_view_and_download_qr(client: AsyncClient):
    offer_id, data, _partner = await _create_partner_link(client)

    viewed = await client.get(f"/api/v1/business/offers/{offer_id}/links/{data['id']}/qr-code")
    _assert_png_response(viewed, attachment=False)

    downloaded = await client.get(
        f"/api/v1/business/offers/{offer_id}/links/{data['id']}/qr-code/download"
    )
    _assert_png_response(downloaded, attachment=True, short_code=data["short_code"])
