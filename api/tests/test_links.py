import re

import pytest
from httpx import AsyncClient


from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


async def _register_and_setup(client: AsyncClient) -> tuple[str, AsyncClient]:
    await register_business(client, "offer-url@example.com")

    offer = await client.post("/api/v1/business/offers", json=offer_payload(
        name="CRM Pro",
        description="No destination on offer",
        product_url="https://crmpro.example.com/pricing",
        conversion_type="sale",
        status="active",
        access_policy="open",
        visibility="public",
        category="SaaS",
        geo="RU",
        allowed_traffic=["seo", "telegram"],
    ))
    assert offer.status_code == 200
    offer_id = offer.json()["id"]
    assert "destination_url" not in offer.json()

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.status_code == 200
    assert "destination_url" not in detail.json()

    partner = await partner_with_access(offer_id, "offer-url-partner@example.com", "Offer Partner")
    return offer_id, partner


@pytest.mark.asyncio
async def test_create_offer_without_destination_url(client: AsyncClient):
    await register_business(client, "no-dest@example.com")
    response = await client.post("/api/v1/business/offers", json=offer_payload(
        name="Offer without URL",
        status="draft",
    ))
    assert response.status_code == 200
    assert "destination_url" not in response.json()


@pytest.mark.asyncio
async def test_tracking_link_uses_product_url_when_destination_omitted(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    assert created.status_code == 200
    data = created.json()
    assert data["destination_url"].startswith("https://crmpro.example.com/pricing")
    assert data["url"].startswith("https://go.refiq.ru/")
    assert re.fullmatch(r"[a-z0-9]{7}", data["short_code"])
    assert data["name"] == "Telegram"


@pytest.mark.asyncio
async def test_tracking_link_can_still_set_destination_url(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)

    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "destination_url": "https://crmpro.example.com/pricing",
        "name": "Pricing",
        "traffic_source": "seo",
    })
    assert created.status_code == 200
    data = created.json()
    assert data["destination_url"].startswith("https://crmpro.example.com/pricing")
    assert re.fullmatch(r"[a-z0-9]{7}", data["short_code"])


@pytest.mark.asyncio
async def test_tracker_redirects_from_tracking_link_only(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "destination_url": "https://crmpro.example.com/pricing",
        "name": "Pricing",
        "traffic_source": "seo",
    })
    assert created.status_code == 200
    short_code = created.json()["short_code"]
    destination_url = created.json()["destination_url"]

    assert re.fullmatch(r"[a-z0-9]{7}", short_code)

    response = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == destination_url

    missing = await client.get("/go/zzzzzzz", follow_redirects=False)
    if short_code != "zzzzzzz":
        assert missing.status_code == 404

    invalid = await client.get("/go/ABC1234", follow_redirects=False)
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_create_link_rejects_forbidden_traffic_source(client: AsyncClient):
    await register_business(client, "traffic-rules@example.com")
    offer = await client.post("/api/v1/business/offers", json=offer_payload(
        name="CRM Pro",
        product_url="https://crmpro.example.com/pricing",
        status="active",
        access_policy="open",
        visibility="public",
        allowed_traffic=["seo", "telegram"],
    ))
    assert offer.status_code == 200
    offer_id = offer.json()["id"]

    partner = await partner_with_access(offer_id, "traffic-rules-partner@example.com")

    rejected = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "PPC",
        "traffic_source": "ppc",
    })
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "TRAFFIC_SOURCE_NOT_ALLOWED"

    listed = await partner.get("/api/v1/partner/campaigns")
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "SEO — статья",
        "traffic_source": "seo",
    })
    assert created.status_code == 200
    assert created.json()["campaign_id"] is not None

    links = await partner.get("/api/v1/partner/links")
    assert links.status_code == 200
    item = links.json()["items"][0]
    assert item["offer_name"] == "CRM Pro"
    assert item["name"] == "SEO — статья"


@pytest.mark.asyncio
async def test_partner_links_list_includes_summary_and_stats(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram — основной",
        "traffic_source": "telegram",
    })
    assert created.status_code == 200

    listed = await partner.get("/api/v1/partner/links")
    assert listed.status_code == 200
    payload = listed.json()
    assert "summary" in payload
    assert payload["summary"]["active_links"] == 1
    assert "filter_options" in payload
    assert len(payload["filter_options"]["offers"]) == 1
    item = payload["items"][0]
    assert "stats" in item
    assert item["stats"]["has_stat_data"] is False
    assert item["stats"]["clicks"] is None


@pytest.mark.asyncio
async def test_partner_can_update_link_metadata(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    link_id = created.json()["id"]

    updated = await partner.patch(f"/api/v1/partner/links/{link_id}", json={
        "name": "Telegram — основной канал",
        "notes": "Закреп",
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "Telegram — основной канал"
    assert updated.json()["notes"] == "Закреп"


@pytest.mark.asyncio
async def test_partner_can_reactivate_disabled_link(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    assert created.status_code == 200
    link_id = created.json()["id"]
    short_code = created.json()["short_code"]
    campaign_id = created.json()["campaign_id"]
    destination = created.json()["destination_url"]

    disabled = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "DISABLED"})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    assert disabled.json()["short_code"] == short_code
    assert disabled.json()["campaign_id"] == campaign_id

    blocked = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert blocked.status_code == 404

    activated = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "ACTIVE"})
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"
    assert activated.json()["short_code"] == short_code
    assert activated.json()["campaign_id"] == campaign_id
    assert activated.json()["destination_url"] == destination
    assert activated.json()["id"] == link_id

    again = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "ACTIVE"})
    assert again.status_code == 200
    assert again.json()["status"] == "ACTIVE"
    assert again.json()["short_code"] == short_code

    redirected = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert redirected.status_code == 302
    assert redirected.headers["location"] == destination


@pytest.mark.asyncio
async def test_cannot_activate_link_when_offer_paused(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    link_id = created.json()["id"]
    await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "DISABLED"})

    paused = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "paused"})
    assert paused.status_code == 200

    activated = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "ACTIVE"})
    assert activated.status_code == 403
    assert activated.json()["error"]["code"] == "OFFER_PAUSED"
    assert "приостановлен" in activated.json()["error"]["message"]

    listed = await partner.get("/api/v1/partner/links")
    item = next(row for row in listed.json()["items"] if row["id"] == link_id)
    assert item["status"] == "DISABLED"


@pytest.mark.asyncio
async def test_cannot_activate_link_when_offer_archived(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": offer_id,
        "name": "Telegram",
        "traffic_source": "telegram",
    })
    link_id = created.json()["id"]
    await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "DISABLED"})

    archived = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "archived"})
    assert archived.status_code == 200

    activated = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "ACTIVE"})
    assert activated.status_code == 403
    assert activated.json()["error"]["code"] == "OFFER_UNAVAILABLE"
    assert activated.json()["error"]["message"] == "Оффер больше недоступен для продвижения."


@pytest.mark.asyncio
async def test_partner_cannot_change_destination_url(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await create_partner_link(
        partner, offer_id, destination_url="https://crmpro.example.com/pricing"
    )
    original = created["destination_url"]

    patched = await partner.patch(
        f"/api/v1/partner/links/{created['id']}",
        json={"destination_url": "https://crmpro.example.com/new-landing"},
    )
    assert patched.status_code == 403
    assert patched.json()["error"]["code"] == "DESTINATION_EDIT_FORBIDDEN"

    listed = await partner.get("/api/v1/partner/links")
    item = next(row for row in listed.json()["items"] if row["id"] == created["id"])
    assert item["destination_url"] == original
    assert "destination_url" in item


@pytest.mark.asyncio
async def test_business_can_update_destination_url_without_changing_public_link(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await create_partner_link(
        partner, offer_id, destination_url="https://crmpro.example.com/pricing"
    )
    link_id = created["id"]
    short_code = created["short_code"]
    campaign_id = created["campaign_id"]
    public_url = created["url"]
    old_destination = created["destination_url"]

    first_click = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert first_click.status_code == 302
    assert first_click.headers["location"] == old_destination

    offer_detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert offer_detail.status_code == 200
    assert "destination_url" not in offer_detail.json()
    promo = next(row for row in offer_detail.json()["promotion_links"] if row["id"] == link_id)
    assert promo["destination_url"] == old_destination
    assert promo["short_code"] == short_code

    updated = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{link_id}",
        json={"destination_url": "https://crmpro.example.com/new-landing"},
    )
    assert updated.status_code == 200
    data = updated.json()
    assert data["destination_url"] == "https://crmpro.example.com/new-landing"
    assert data["short_code"] == short_code
    assert data["url"] == public_url
    assert data["campaign_id"] == campaign_id
    assert data["status"] == "ACTIVE"
    assert data["id"] == link_id

    history = await client.get(f"/api/v1/business/offers/{offer_id}/links/{link_id}/destination-history")
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["destination_url"] == "https://crmpro.example.com/new-landing"
    assert items[0]["previous_url"] == old_destination
    assert items[0]["actor_name"]

    second_click = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert second_click.status_code == 302
    assert second_click.headers["location"] == "https://crmpro.example.com/new-landing"

    from sqlalchemy import select
    from app.modules.links.models import Click
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        clicks = (await session.execute(select(Click).order_by(Click.id))).scalars().all()
        assert len(clicks) == 2
        assert clicks[0].tracking_link_id == int(link_id)
        assert clicks[1].tracking_link_id == int(link_id)
        assert "destination_url" not in Click.__table__.c
        assert re.fullmatch(r"[a-z0-9]{12}", clicks[0].rqcid)
        assert re.fullmatch(r"[a-z0-9]{12}", clicks[1].rqcid)


@pytest.mark.asyncio
async def test_business_can_update_disabled_link_destination_without_activating(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await create_partner_link(
        partner, offer_id, destination_url="https://crmpro.example.com/pricing"
    )
    link_id = created["id"]
    short_code = created["short_code"]

    disabled = await partner.patch(f"/api/v1/partner/links/{link_id}", json={"status": "DISABLED"})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"

    updated = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{link_id}",
        json={"destination_url": "https://crmpro.example.com/new-landing"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "DISABLED"
    assert updated.json()["destination_url"] == "https://crmpro.example.com/new-landing"
    assert updated.json()["short_code"] == short_code

    blocked = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert blocked.status_code == 404


@pytest.mark.asyncio
async def test_business_destination_url_validation(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await create_partner_link(
        partner, offer_id, destination_url="https://crmpro.example.com/pricing"
    )

    invalid = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{created['id']}",
        json={"destination_url": "not-a-url"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_DESTINATION_URL"
    assert invalid.json()["error"]["message"] == "Введите корректный URL"

    looped = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{created['id']}",
        json={"destination_url": "https://go.refiq.ru/a7k3m2q"},
    )
    assert looped.status_code == 400
    assert looped.json()["error"]["code"] == "DESTINATION_DOMAIN_FORBIDDEN"


@pytest.mark.asyncio
async def test_other_business_cannot_update_destination_url(client: AsyncClient):
    offer_id, partner = await _register_and_setup(client)
    created = await create_partner_link(
        partner, offer_id, destination_url="https://crmpro.example.com/pricing"
    )
    link_id = created["id"]

    await register_business(client, "other-dest@example.com")
    response = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{link_id}",
        json={"destination_url": "https://crmpro.example.com/hijack"},
    )
    assert response.status_code == 404

