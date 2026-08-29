import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sites.backfill import backfill_sites
from app.modules.sites.domain import hostname_from_url, normalize_site_input
from app.modules.sites.models import Site
from tests.conftest import engine
from tests.helpers import become_partner, register_business


def test_normalize_site_input_strips_path_query_and_scheme():
    domain, suggested = normalize_site_input("https://Shop.Example.ru/catalog?x=1")
    assert domain == "shop.example.ru"
    assert suggested == "shop.example.ru"


def test_normalize_site_input_keeps_distinct_hostnames():
    assert normalize_site_input("example.ru")[0] == "example.ru"
    assert normalize_site_input("https://shop.example.ru/")[0] == "shop.example.ru"
    assert normalize_site_input("http://promo.example.ru")[0] == "promo.example.ru"


def test_normalize_site_input_rejects_invalid():
    from app.core.exceptions import AppError

    with pytest.raises(AppError) as exc:
        normalize_site_input("not a url")
    assert exc.value.code == "INVALID_SITE_URL"


def test_hostname_from_url_none_on_empty():
    assert hostname_from_url("") is None
    assert hostname_from_url("https://crmpro.example.com/pricing") == "crmpro.example.com"


@pytest.mark.asyncio
async def test_create_and_list_sites(client: AsyncClient):
    await register_business(client, "sites-create@example.com")

    created = await client.post(
        "/api/v1/business/sites",
        json={"url": "https://shop.example.ru/catalog?x=1", "name": "Интернет-магазин"},
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["domain"] == "shop.example.ru"
    assert data["name"] == "Интернет-магазин"
    assert data["status"] == "active"
    assert data["display_status"] == "needs_setup"
    assert data["sdk_status"] == "not_detected"
    assert data["can_delete"] is True
    assert len(data["site_key"]) == 5

    listed = await client.get("/api/v1/business/sites")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == data["id"]


@pytest.mark.asyncio
async def test_duplicate_domain_same_business_conflict(client: AsyncClient):
    await register_business(client, "sites-dup@example.com")
    first = await client.post("/api/v1/business/sites", json={"url": "https://shop.example.ru"})
    assert first.status_code == 200
    again = await client.post("/api/v1/business/sites", json={"url": "SHOP.example.ru/"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_same_domain_allowed_for_other_business(client: AsyncClient):
    await register_business(client, "sites-a@example.com", name="A", website="https://a.example.com")
    first = await client.post("/api/v1/business/sites", json={"url": "https://shared.example.com"})
    assert first.status_code == 200

    await register_business(client, "sites-b@example.com", name="B", website="https://b.example.com")
    second = await client.post("/api/v1/business/sites", json={"url": "https://shared.example.com"})
    assert second.status_code == 200
    assert second.json()["site_key"] != first.json()["site_key"]


@pytest.mark.asyncio
async def test_update_disable_enable_delete_unused_site(client: AsyncClient):
    await register_business(client, "sites-lifecycle@example.com")
    created = await client.post("/api/v1/business/sites", json={"url": "https://one.example.com"})
    site_id = created.json()["id"]

    renamed = await client.patch(f"/api/v1/business/sites/{site_id}", json={"name": "Основной сайт"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Основной сайт"

    disabled = await client.post(f"/api/v1/business/sites/{site_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert disabled.json()["display_status"] == "disabled"
    assert disabled.json()["disabled_at"] is not None

    enabled = await client.post(f"/api/v1/business/sites/{site_id}/enable")
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"
    assert enabled.json()["disabled_at"] is None

    deleted = await client.delete(f"/api/v1/business/sites/{site_id}")
    assert deleted.status_code == 204
    listed = await client.get("/api/v1/business/sites")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_cannot_delete_site_used_by_tracking_link(client: AsyncClient):
    await register_business(client, "sites-used@example.com")
    site = await client.post("/api/v1/business/sites", json={"url": "https://crmpro.example.com"})
    assert site.status_code == 200
    site_id = site.json()["id"]

    offer = await client.post(
        "/api/v1/business/offers",
        json={
            "name": "CRM Pro",
            "product_url": "https://crmpro.example.com/pricing",
            "status": "active",
            "access_policy": "open",
            "visibility": "public",
        },
    )
    offer_id = offer.json()["id"]
    await become_partner(client, "Site Owner")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    created = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": offer_id, "name": "TG", "traffic_source": "telegram"},
    )
    assert created.status_code == 200

    await client.post("/api/v1/me/context", json={"role": "business"})
    blocked = await client.delete(f"/api/v1/business/sites/{site_id}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SITE_IN_USE"


@pytest.mark.asyncio
async def test_site_ownership(client: AsyncClient):
    await register_business(client, "sites-owner@example.com")
    created = await client.post("/api/v1/business/sites", json={"url": "https://mine.example.com"})
    site_id = created.json()["id"]

    await register_business(client, "sites-other@example.com", name="Other", website="https://other.example.com")
    missing = await client.get(f"/api/v1/business/sites/{site_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_tracking_link_matches_site_and_unknown_host_does_not_block(client: AsyncClient):
    await register_business(client, "sites-match@example.com")
    await client.post("/api/v1/business/sites", json={"url": "https://crmpro.example.com"})

    offer = await client.post(
        "/api/v1/business/offers",
        json={
            "name": "CRM Pro",
            "product_url": "https://crmpro.example.com/pricing",
            "status": "active",
            "access_policy": "open",
            "visibility": "public",
        },
    )
    offer_id = offer.json()["id"]
    await become_partner(client, "Matcher")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    created = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": offer_id, "name": "TG", "traffic_source": "telegram"},
    )
    assert created.status_code == 200
    link_id = created.json()["id"]

    await client.post("/api/v1/me/context", json={"role": "business"})
    matched = await client.get(f"/api/v1/business/offers/{offer_id}/links/{link_id}")
    assert matched.status_code == 200
    assert matched.json()["site_missing"] is False
    assert matched.json()["site_domain"] == "crmpro.example.com"

    unknown = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{link_id}",
        json={"destination_url": "https://landing.example.com/promo"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["destination_url"] == "https://landing.example.com/promo"
    assert unknown.json()["site_missing"] is True
    assert unknown.json()["site_id"] is None
    assert unknown.json()["site_domain"] == "landing.example.com"


@pytest.mark.asyncio
async def test_sdk_event_with_site_id_marks_connected(client: AsyncClient):
    await register_business(client, "sites-event@example.com")
    site = await client.post("/api/v1/business/sites", json={"url": "https://app.example.com"})
    site_key = site.json()["site_key"]
    site_id = site.json()["id"]

    accepted = await client.post(
        "/event",
        content='{"event":"page_view","site_id":"%s","script_id":"%s","rqcid":"abc123xyz789"}' % (site_key, site_key),
        headers={"Content-Type": "text/plain;charset=UTF-8"},
    )
    assert accepted.status_code == 204

    checked = await client.post(f"/api/v1/business/sites/{site_id}/check")
    assert checked.status_code == 200
    assert checked.json()["sdk_status"] == "connected"
    assert checked.json()["display_status"] == "connected"
    assert checked.json()["last_success_at"] is not None
    assert checked.json()["can_delete"] is False


@pytest.mark.asyncio
async def test_legacy_sdk_credential_creates_site_from_website(client: AsyncClient):
    await register_business(client, "sites-legacy-sdk@example.com")
    created = await client.post("/api/v1/business/sdk/credential")
    assert created.status_code == 200
    sites = await client.get("/api/v1/business/sites")
    assert len(sites.json()) == 1
    assert sites.json()[0]["domain"] == "acme.example.com"
    assert sites.json()[0]["site_key"] == created.json()["script_id"]


@pytest.mark.asyncio
async def test_backfill_creates_site_from_legacy_script_and_website(client: AsyncClient, db: AsyncSession):
    await register_business(client, "sites-backfill@example.com", website="https://legacy.example.com/home")
    business_id = (await client.get("/api/v1/business/settings")).json()["id"]

    await db.execute(
        text(
            """
            INSERT INTO sdk_scripts (business_id, script_id, created_at)
            VALUES (:business_id, 'ab12c', CURRENT_TIMESTAMP)
            """
        ),
        {"business_id": int(business_id)},
    )
    await db.commit()

    async with engine.begin() as conn:
        await conn.run_sync(backfill_sites)

    db.expire_all()
    site = (await db.execute(text("SELECT domain, site_key FROM sites WHERE business_id = :id"), {"id": int(business_id)})).one()
    assert site[0] == "legacy.example.com"
    assert site[1] == "ab12c"
    linked = (
        await db.execute(text("SELECT site_id FROM sdk_scripts WHERE script_id = 'ab12c'"))
    ).scalar_one()
    assert linked is not None
    from sqlalchemy import select

    stored = (await db.execute(select(Site).where(Site.site_key == "ab12c"))).scalar_one()
    assert stored.domain == "legacy.example.com"
