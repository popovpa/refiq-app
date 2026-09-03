import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import fastapi_app
from tests.helpers import become_partner, register_business, register_user


async def _register_business(client: AsyncClient, email: str = "biz-offer@example.com") -> None:
    await register_business(client, email)


async def _external_partner(email: str, display_name: str = "Partner") -> AsyncClient:
    transport = ASGITransport(app=fastapi_app)
    partner = AsyncClient(transport=transport, base_url="http://test")
    await register_user(partner, email)
    await become_partner(partner, display_name)
    switch = await partner.post("/api/v1/me/context", json={"role": "partner"})
    assert switch.status_code == 200
    return partner


@pytest.mark.asyncio
async def test_business_offer_lifecycle(client: AsyncClient):
    await _register_business(client)
    created = await client.post("/api/v1/business/offers", json={
        "name": "CRM Pro",
        "description": "Партнёрка CRM",
        "category": "SaaS",
        "geo": "RU",
        "conversion_type": "sale",
        "commission_type": "percent",
        "commission_value": 20,
        "attribution_window_days": 30,
        "access_policy": "approval",
        "allowed_traffic": ["seo", "telegram"],
        "forbidden_traffic": ["ppc"],
        "partner_notes": "Без брендовых запросов",
        "status": "draft",
        "product_url": "https://crmpro.example.com",
    })
    assert created.status_code == 200
    data = created.json()
    assert "destination_url" not in data
    offer_id = data["id"]
    assert data["status"] == "draft"
    assert data["category"] == "SaaS"
    assert data["allowed_traffic"] == ["seo", "telegram"]

    published = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "active"})
    assert published.status_code == 200

    paused = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "paused"})
    assert paused.status_code == 200

    resumed = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "active"})
    assert resumed.status_code == 200

    archived = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "archived"})
    assert archived.status_code == 200

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"
    assert "destination_url" not in detail.json()
    assert detail.json()["kpis"]["clicks"] == 0


@pytest.mark.asyncio
async def test_partner_approval_and_link_flow(client: AsyncClient):
    await _register_business(client, "approval-biz@example.com")
    created = await client.post("/api/v1/business/offers", json={
        "name": "TaskFlow",
        "description": "Регистрации",
        "category": "SaaS",
        "access_policy": "approval",
        "status": "active",
        "product_url": "https://taskflow.example.com",
        "commission_type": "fixed",
        "commission_value": 500,
    })
    assert created.status_code == 200
    offer_id = created.json()["id"]

    partner = await _external_partner("approval-partner@example.com", "Мария")
    try:
        catalog = await partner.get("/api/v1/partner/offers/marketplace")
        assert catalog.status_code == 200
        assert any(item["id"] == offer_id for item in catalog.json()["items"])
        assert next(item for item in catalog.json()["items"] if item["id"] == offer_id)["is_own_offer"] is False

        join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join", json={
            "comment": "Веду Telegram-канал",
            "traffic_sources": ["telegram"],
            "geo": "RU",
        })
        assert join.status_code == 200
        assert join.json()["status"] == "pending"

        blocked_link = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "TG",
            "traffic_source": "telegram",
        })
        assert blocked_link.status_code == 403

        detail = await client.get(f"/api/v1/business/offers/{offer_id}")
        assert detail.status_code == 200
        pending = detail.json()["pending_applications"]
        assert len(pending) == 1
        access_id = pending[0]["id"]

        approve = await client.post(f"/api/v1/business/offers/{offer_id}/partners/{access_id}/approve")
        assert approve.status_code == 200

        link = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "Telegram",
            "traffic_source": "telegram",
        })
        assert link.status_code == 200
        assert link.json()["url"].startswith("https://go.refiq.ru/")
        assert "offer_id" in link.json()
    finally:
        await partner.aclose()


@pytest.mark.asyncio
async def test_invite_only_cannot_self_join(client: AsyncClient):
    await _register_business(client, "invite-biz@example.com")
    created = await client.post("/api/v1/business/offers", json={
        "name": "Private Offer",
        "access_policy": "invite_only",
        "status": "active",
        "product_url": "https://private.example.com",
    })
    offer_id = created.json()["id"]
    partner = await _external_partner("invite-guest@example.com", "Guest")
    try:
        join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert join.status_code == 403
    finally:
        await partner.aclose()


@pytest.mark.asyncio
async def test_cancel_pending_request(client: AsyncClient):
    await _register_business(client, "cancel-biz@example.com")
    created = await client.post("/api/v1/business/offers", json={
        "name": "Lead Offer",
        "access_policy": "approval",
        "status": "active",
        "product_url": "https://lead.example.com",
    })
    offer_id = created.json()["id"]
    partner = await _external_partner("cancel-partner@example.com", "Applicant")
    try:
        join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert join.json()["status"] == "pending"
        cancel = await partner.post(f"/api/v1/partner/offers/{offer_id}/cancel-request")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"
    finally:
        await partner.aclose()


@pytest.mark.asyncio
async def test_offer_detail_counts_clicks_per_link(client: AsyncClient):
    await _register_business(client, "link-stats-biz@example.com")
    created = await client.post("/api/v1/business/offers", json={
        "name": "Stats Offer",
        "access_policy": "open",
        "status": "active",
        "product_url": "https://stats.example.com/pricing",
        "commission_type": "percent",
        "commission_value": 10,
    })
    assert created.status_code == 200
    offer_id = created.json()["id"]

    partner = await _external_partner("stats-partner@example.com", "Stats Partner")
    try:
        join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert join.status_code == 200

        first = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "Telegram",
            "traffic_source": "telegram",
        })
        second = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "SEO",
            "traffic_source": "seo",
        })
        assert first.status_code == 200
        assert second.status_code == 200

        clicked = await partner.get(f"/go/{first.json()['short_code']}", follow_redirects=False)
        assert clicked.status_code == 302
        first_id = first.json()["id"]
        second_id = second.json()["id"]
    finally:
        await partner.aclose()

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["kpis"]["clicks"] == 1
    assert data["kpis"]["conversions"] == 0
    assert data["kpis"]["approved_conversions"] == 0
    assert sum(item["clicks"] for item in data["promotion_links"]) == 1
    assert sum(item["clicks"] for item in data["partners"]) == 1

    by_id = {str(item["id"]): item for item in data["promotion_links"]}
    assert by_id[str(first_id)]["clicks"] == 1
    assert by_id[str(second_id)]["clicks"] == 0
    assert by_id[str(second_id)]["conversions"] == 0


@pytest.mark.asyncio
async def test_partner_catalog_includes_promotion_status(client: AsyncClient):
    await _register_business(client, "promo-card-biz@example.com")
    created = await client.post("/api/v1/business/offers", json={
        "name": "Promo Offer",
        "access_policy": "open",
        "status": "active",
        "product_url": "https://promo.example.com/pricing",
        "commission_type": "percent",
        "commission_value": 10,
    })
    assert created.status_code == 200
    offer_id = created.json()["id"]

    partner = await _external_partner("promo-partner@example.com", "Promo Partner")
    try:
        join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert join.status_code == 200

        catalog = await partner.get("/api/v1/partner/offers/marketplace")
        assert catalog.status_code == 200
        item = next(row for row in catalog.json()["items"] if row["id"] == offer_id)
        assert item["is_own_offer"] is False
        assert item["promotion_status"] == "NOT_STARTED"
        assert item["active_links_count"] == 0
        assert item["total_links_count"] == 0
        assert item["partner_clicks"] == 0

        first = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "Telegram",
            "traffic_source": "telegram",
        })
        second = await partner.post("/api/v1/partner/links", json={
            "offer_id": offer_id,
            "name": "SEO",
            "traffic_source": "seo",
        })
        assert first.status_code == 200
        assert second.status_code == 200
        clicked = await partner.get(f"/go/{first.json()['short_code']}", follow_redirects=False)
        assert clicked.status_code == 302

        catalog = await partner.get("/api/v1/partner/offers/marketplace")
        item = next(row for row in catalog.json()["items"] if row["id"] == offer_id)
        assert item["promotion_status"] == "ACTIVE"
        assert item["active_links_count"] == 2
        assert item["total_links_count"] == 2
        assert item["partner_clicks"] == 1
        assert item["partner_conversions"] == 0

        mine = await partner.get("/api/v1/partner/offers")
        mine_item = next(row for row in mine.json()["items"] if row["id"] == offer_id)
        assert mine_item["promotion_status"] == "ACTIVE"
        assert mine_item["active_links_count"] == 2

        disabled_first = await partner.patch(f"/api/v1/partner/links/{first.json()['id']}", json={"status": "DISABLED"})
        disabled_second = await partner.patch(f"/api/v1/partner/links/{second.json()['id']}", json={"status": "DISABLED"})
        assert disabled_first.status_code == 200
        assert disabled_second.status_code == 200

        catalog = await partner.get("/api/v1/partner/offers/marketplace")
        item = next(row for row in catalog.json()["items"] if row["id"] == offer_id)
        assert item["promotion_status"] == "PAUSED"
        assert item["active_links_count"] == 0
        assert item["total_links_count"] == 2
    finally:
        await partner.aclose()
