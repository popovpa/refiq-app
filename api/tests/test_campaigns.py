import pytest
from httpx import AsyncClient

from tests.test_links import _register_and_setup


@pytest.mark.asyncio
async def test_create_tracking_link_creates_general_campaign(client: AsyncClient):
    offer_id = await _register_and_setup(client)
    created = await client.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram — основной канал",
        "traffic_source": "telegram",
    })
    assert created.status_code == 200
    data = created.json()
    assert data["campaign_id"] is not None
    assert data["name"] == "Telegram — основной канал"
    assert data["traffic_source"] == "telegram"
    assert data["status"] == "ACTIVE"
    assert data["offer_name"] == "CRM Pro"
    assert data["url"].startswith("https://go.refiq.ru/")

    campaigns = await client.get("/api/v1/partner/campaigns")
    assert campaigns.status_code == 200
    campaign = next(row for row in campaigns.json()["items"] if row["id"] == data["campaign_id"])
    assert campaign["name"] == "Telegram — основной канал"
    assert campaign["type"] == "GENERAL"
    assert campaign["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_campaign_lifecycle_for_tracking_links(client: AsyncClient):
    offer_id = await _register_and_setup(client)

    campaign = await client.post("/api/v1/partner/campaigns", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "description": "Канал",
    })
    assert campaign.status_code == 200
    campaign_id = campaign.json()["id"]
    assert campaign.json()["status"] == "ACTIVE"

    created = await client.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "destination_url": "https://crmpro.example.com/pricing",
        "campaign_id": campaign_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    assert created.status_code == 200
    assert created.json()["campaign_id"] == campaign_id
    link_status = created.json()["status"]

    archived = await client.patch(f"/api/v1/partner/campaigns/{campaign_id}", json={"status": "ARCHIVED"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"

    links = await client.get("/api/v1/partner/links")
    assert links.status_code == 200
    item = next(row for row in links.json()["items"] if row["campaign_id"] == campaign_id)
    assert item["status"] == link_status

    rejected = await client.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "destination_url": "https://crmpro.example.com/blog",
        "campaign_id": campaign_id,
        "name": "Blog",
        "traffic_source": "content",
    })
    assert rejected.status_code == 403

    restored = await client.patch(f"/api/v1/partner/campaigns/{campaign_id}", json={"status": "ACTIVE"})
    assert restored.status_code == 200

    listed = await client.get(f"/api/v1/partner/campaigns?offer_id={offer_id}&status=ACTIVE")
    assert listed.status_code == 200
    assert any(row["id"] == campaign_id for row in listed.json()["items"])
