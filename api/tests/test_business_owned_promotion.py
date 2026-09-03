import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click
from tests.conftest import fastapi_app
from tests.helpers import become_partner, register_business, register_user


async def _create_active_offer(client: AsyncClient, email: str) -> str:
    await register_business(client, email)
    offer = await client.post("/api/v1/business/offers", json={
        "name": "CRM Pro",
        "product_url": "https://crmpro.example.com/pricing",
        "status": "active",
        "access_policy": "open",
        "visibility": "public",
        "commission_type": "percent",
        "commission_value": 10,
    })
    assert offer.status_code == 200, offer.text
    return str(offer.json()["id"])


async def _external_partner(email: str, display_name: str) -> AsyncClient:
    transport = ASGITransport(app=fastapi_app)
    partner = AsyncClient(transport=transport, base_url="http://test")
    await register_user(partner, email)
    await become_partner(partner, display_name)
    switch = await partner.post("/api/v1/me/context", json={"role": "partner"})
    assert switch.status_code == 200
    return partner


async def _partner_link(partner: AsyncClient, offer_id: str, name: str = "Telegram") -> dict:
    join = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200, join.text
    created = await partner.post("/api/v1/partner/links", json={
        "offer_id": int(offer_id),
        "name": name,
        "traffic_source": "telegram",
    })
    assert created.status_code == 200, created.text
    return created.json()


@pytest.mark.asyncio
async def test_business_can_create_campaign_and_link_without_partner(client: AsyncClient):
    offer_id = await _create_active_offer(client, "biz-own@example.com")

    campaign = await client.post(f"/api/v1/business/offers/{offer_id}/campaigns", json={
        "name": "Яндекс Директ",
        "description": "Поиск",
    })
    assert campaign.status_code == 200, campaign.text
    data = campaign.json()
    assert data["owner_type"] == "business"
    assert data["business_id"] is not None
    assert data["partner_id"] is None
    assert data["offer_id"] == int(offer_id)

    without_campaign = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    assert without_campaign.status_code == 200, without_campaign.text
    link = without_campaign.json()
    assert link["owner_type"] == "business"
    assert link["partner_id"] is None
    assert link["campaign_id"] is None
    assert link["destination_url"].startswith("https://crmpro.example.com/pricing")

    with_campaign = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/promo",
        "campaign_id": data["id"],
        "name": "Promo",
    })
    assert with_campaign.status_code == 200, with_campaign.text
    assert with_campaign.json()["campaign_id"] == data["id"]
    assert with_campaign.json()["campaign_name"] == "Яндекс Директ"

    listed = await client.get(f"/api/v1/business/offers/{offer_id}/links")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2
    assert all(item["owner_type"] == "business" for item in listed.json()["items"])

    campaigns = await client.get(f"/api/v1/business/offers/{offer_id}/campaigns")
    assert campaigns.status_code == 200
    assert campaigns.json()["items"][0]["links_count"] == 1

    renamed = await client.patch(
        f"/api/v1/business/offers/{offer_id}/campaigns/{data['id']}",
        json={"name": "VK Ads", "description": "Ретаргетинг"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "VK Ads"
    assert renamed.json()["description"] == "Ретаргетинг"
    assert renamed.json()["offer_id"] == int(offer_id)
    assert renamed.json()["business_id"] == data["business_id"]
    assert renamed.json()["partner_id"] is None


@pytest.mark.asyncio
async def test_business_link_requires_destination_and_active_offer(client: AsyncClient):
    offer_id = await _create_active_offer(client, "biz-dest@example.com")
    missing = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={})
    assert missing.status_code == 422

    paused = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"status": "paused"})
    assert paused.status_code == 200
    rejected_link = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    assert rejected_link.status_code == 403
    assert rejected_link.json()["error"]["code"] == "OFFER_UNAVAILABLE"

    rejected_campaign = await client.post(f"/api/v1/business/offers/{offer_id}/campaigns", json={"name": "Ads"})
    assert rejected_campaign.status_code == 403


@pytest.mark.asyncio
async def test_archived_campaign_blocks_new_links_but_keeps_existing(client: AsyncClient):
    offer_id = await _create_active_offer(client, "biz-archive@example.com")
    campaign = await client.post(f"/api/v1/business/offers/{offer_id}/campaigns", json={"name": "Ads"})
    campaign_id = campaign.json()["id"]
    created = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
        "campaign_id": campaign_id,
    })
    assert created.status_code == 200
    short_code = created.json()["short_code"]

    archived = await client.patch(
        f"/api/v1/business/offers/{offer_id}/campaigns/{campaign_id}",
        json={"status": "ARCHIVED"},
    )
    assert archived.status_code == 200
    blocked = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/blog",
        "campaign_id": campaign_id,
    })
    assert blocked.status_code == 403

    still_works = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert still_works.status_code == 302

    restored = await client.patch(
        f"/api/v1/business/offers/{offer_id}/campaigns/{campaign_id}",
        json={"status": "ACTIVE"},
    )
    assert restored.status_code == 200
    again = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/blog",
        "campaign_id": campaign_id,
    })
    assert again.status_code == 200


@pytest.mark.asyncio
async def test_disabled_business_link_stops_clicks_and_keeps_history(client: AsyncClient, db: AsyncSession):
    offer_id = await _create_active_offer(client, "biz-disable@example.com")
    created = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    link_id = created.json()["id"]
    short_code = created.json()["short_code"]
    clicked = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert clicked.status_code == 302

    disabled = await client.patch(
        f"/api/v1/business/offers/{offer_id}/links/{link_id}/status",
        json={"status": "DISABLED"},
    )
    assert disabled.status_code == 200
    blocked = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert blocked.status_code == 404

    db.expire_all()
    clicks = (await db.execute(select(Click).where(Click.tracking_link_id == link_id))).scalars().all()
    assert len(clicks) == 1


@pytest.mark.asyncio
async def test_cannot_mix_business_and_partner_campaign_ownership(client: AsyncClient):
    offer_id = await _create_active_offer(client, "biz-mix@example.com")
    business_campaign = await client.post(f"/api/v1/business/offers/{offer_id}/campaigns", json={"name": "Own"})
    business_campaign_id = business_campaign.json()["id"]

    partner = await _external_partner("mix-partner@example.com", "Mix Partner")
    try:
        partner_link_attempt = await _partner_link(partner, offer_id)
        partner_campaign_id = partner_link_attempt["campaign_id"]
        mixed = await partner.post("/api/v1/partner/links", json={
            "offer_id": int(offer_id),
            "name": "Wrong",
            "traffic_source": "content",
            "campaign_id": business_campaign_id,
        })
        assert mixed.status_code == 403
    finally:
        await partner.aclose()

    mixed_own = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
        "campaign_id": partner_campaign_id,
    })
    assert mixed_own.status_code == 403


@pytest.mark.asyncio
async def test_partner_ui_does_not_see_business_owned_links(client: AsyncClient):
    offer_id = await _create_active_offer(client, "biz-hide@example.com")
    own = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    assert own.status_code == 200
    own_id = own.json()["id"]

    partner_client = await _external_partner("hidden-partner@example.com", "Hidden Partner")
    try:
        partner = await _partner_link(partner_client, offer_id)
        listed = await partner_client.get("/api/v1/partner/links")
        assert listed.status_code == 200
        ids = {item["id"] for item in listed.json()["items"]}
        assert partner["id"] in ids
        assert own_id not in ids

        campaigns = await partner_client.get("/api/v1/partner/campaigns")
        assert all(item["owner_type"] == "partner" for item in campaigns.json()["items"])
    finally:
        await partner_client.aclose()

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    partner_ids = {item["id"] for item in detail.json()["promotion_links"]}
    assert own_id not in partner_ids
    assert partner["id"] in partner_ids
    assert "own" in detail.json()["traffic_split"]
    assert "partner" in detail.json()["traffic_split"]


@pytest.mark.asyncio
async def test_dual_role_business_create_is_not_bound_to_partner(client: AsyncClient):
    offer_id = await _create_active_offer(client, "both-promo@example.com")
    await become_partner(client, "Both Roles")
    await client.post("/api/v1/me/context", json={"role": "business"})
    created = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    assert created.status_code == 200
    assert created.json()["owner_type"] == "business"
    assert created.json()["partner_id"] is None

    await client.post("/api/v1/me/context", json={"role": "partner"})
    listed = await client.get("/api/v1/partner/links")
    assert listed.json()["items"] == []


@pytest.mark.asyncio
async def test_business_owned_conversion_has_no_partner_commission(client: AsyncClient, db: AsyncSession):
    offer_id = await _create_active_offer(client, "biz-conv@example.com")
    created = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    clicked = await client.get(f"/go/{created.json()['short_code']}", follow_redirects=False)
    assert clicked.status_code == 302

    token = (await client.post("/api/v1/business/postback/credential")).json()["token"]
    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    assert click is not None
    rqcid = click.rqcid
    accepted = await client.post(
        "/postback",
        json={"rqcid": rqcid, "amount": 1000, "currency": "RUB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200

    db.expire_all()
    conversion = (await db.execute(select(Conversion).where(Conversion.click_id == rqcid))).scalar_one()
    assert conversion.partner_id is None
    assert conversion.partner_tracking_link_id is None
    assert conversion.tracking_link_id == created.json()["id"]
    assert float(conversion.commission_amount) == 0

    listed = await client.get("/api/v1/business/conversions")
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["partner_name"] is None
    assert item["source_owner"] == "business"

    conversion_id = conversion.id
    approved = await client.post(f"/api/v1/business/conversions/{conversion_id}/approve")
    assert approved.status_code == 200
    db.expire_all()
    commissions = (await db.execute(select(Commission).where(Commission.conversion_id == conversion_id))).scalars().all()
    assert commissions == []


@pytest.mark.asyncio
async def test_business_click_does_not_override_partner_attribution(client: AsyncClient, db: AsyncSession):
    offer_id = await _create_active_offer(client, "attr-biz@example.com")
    partner_client = await _external_partner("attr-partner@example.com", "Attr Partner")
    try:
        partner = await _partner_link(partner_client, offer_id)
        partner_click = await partner_client.get(f"/go/{partner['short_code']}", follow_redirects=False)
        assert partner_click.status_code == 302
        partner_rqcid = partner_client.cookies.get("refiq_prqcid")
        assert partner_rqcid
    finally:
        await partner_client.aclose()

    own = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
        "name": "Own ads",
    })
    assert own.status_code == 200
    client.cookies.set("refiq_prqcid", partner_rqcid)
    own_click = await client.get(f"/go/{own.json()['short_code']}", follow_redirects=False)
    assert own_click.status_code == 302

    token = (await client.post("/api/v1/business/postback/credential")).json()["token"]
    db.expire_all()
    business_click = (
        await db.execute(
            select(Click).where(Click.tracking_link_id == own.json()["id"]).order_by(Click.id.desc())
        )
    ).scalars().first()
    assert business_click is not None
    assert business_click.partner_rqcid is not None
    rqcid = business_click.rqcid

    accepted = await client.post(
        "/postback",
        json={"rqcid": rqcid, "amount": 2000, "currency": "RUB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200

    db.expire_all()
    conversion = (
        await db.execute(select(Conversion).where(Conversion.click_id == rqcid))
    ).scalar_one()
    assert conversion.partner_id == partner["partner_id"]
    assert conversion.tracking_link_id == own.json()["id"]
    assert conversion.partner_tracking_link_id == partner["id"]
    assert float(conversion.commission_amount) == 200

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    split = detail.json()["traffic_split"]
    assert split["own"]["clicks"] == 1
    assert split["own"]["conversions"] == 1
    assert split["partner"]["clicks"] == 1
    assert split["partner"]["conversions"] == 0

    listed = await client.get("/api/v1/business/conversions")
    item = listed.json()["items"][0]
    assert item["source_owner"] == "business"
    assert item["partner_name"]


@pytest.mark.asyncio
async def test_business_conversions_source_owner_filter(client: AsyncClient, db: AsyncSession):
    offer_id = await _create_active_offer(client, "biz-filter@example.com")
    own = await client.post(f"/api/v1/business/offers/{offer_id}/links", json={
        "destination_url": "https://crmpro.example.com/pricing",
    })
    clicked = await client.get(f"/go/{own.json()['short_code']}", follow_redirects=False)
    assert clicked.status_code == 302

    token = (await client.post("/api/v1/business/postback/credential")).json()["token"]
    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    assert click is not None
    accepted = await client.post(
        "/postback",
        json={"rqcid": click.rqcid, "amount": 500, "currency": "RUB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200

    own_only = await client.get("/api/v1/business/conversions?source_owner=business")
    assert own_only.status_code == 200
    assert len(own_only.json()["items"]) == 1
    assert own_only.json()["items"][0]["source_owner"] == "business"

    partner_only = await client.get("/api/v1/business/conversions?source_owner=partner")
    assert partner_only.status_code == 200
    assert partner_only.json()["items"] == []
