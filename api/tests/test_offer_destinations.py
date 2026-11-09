import ast
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.modules.links.models import Click, TrackingLink
from app.modules.offers.destination_model import OfferDestination
from app.modules.offers.destination_service import backfill_legacy_destinations
from app.modules.offers.destination_url import validate_destination_page_url
from tests.conftest import TestingSessionLocal
from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


def _offer_body(**overrides):
    payload = offer_payload()
    payload.update(
        {
            "name": "Смартфоны",
            "description": "Несколько посадочных страниц одного оффера",
            "product_url": "https://phones.example.com/product.html?id=nova-max",
            "status": "active",
            "access_policy": "open",
            "visibility": "public",
            "category": "SaaS",
            "geo": "RU",
            "allowed_traffic": ["seo", "telegram"],
        }
    )
    payload.update(overrides)
    return payload


async def _business_offer(client: AsyncClient, email: str = "dest-business@example.com", **overrides):
    await register_business(client, email)
    created = await client.post("/api/v1/business/offers", json=_offer_body(**overrides))
    assert created.status_code == 200, created.text
    assert "destination_url" not in created.json()
    return created.json()["id"]


async def _pages(client: AsyncClient, offer_id: int):
    response = await client.get(f"/api/v1/business/offers/{offer_id}/destinations")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_legacy_product_url_becomes_primary_destination(client: AsyncClient):
    offer_id = await _business_offer(client)
    pages = await _pages(client, offer_id)
    assert pages["total"] == 1
    primary = pages["items"][0]
    assert primary["is_primary"] is True
    assert primary["status"] == "active"
    assert primary["type"] == "PRODUCT"
    assert primary["url"] == "https://phones.example.com/product.html?id=nova-max"

    partner = await partner_with_access(offer_id, "dest-partner@example.com")
    visible = await partner.get(f"/api/v1/partner/offers/{offer_id}/destinations")
    assert visible.status_code == 200
    assert visible.json()["items"][0]["id"] == primary["id"]
    assert "links_count" not in visible.json()["items"][0]

    created = await partner.post(
        "/api/v1/partner/links",
        json={"offer_id": offer_id, "name": "Старый клиент", "traffic_source": "seo"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["destination_url"] == primary["url"]
    assert created.json()["offer_destination_id"] == primary["id"]
    assert created.json()["short_code"]


@pytest.mark.asyncio
async def test_partner_can_promote_several_pages_and_repeat_one(client: AsyncClient):
    offer_id = await _business_offer(client, "multi-business@example.com")
    second = await client.post(
        f"/api/v1/business/offers/{offer_id}/destinations",
        json={
            "title": "Pulse Phone SE",
            "url": "https://phones.example.com/product.html?id=pulse-se",
            "type": "PRODUCT",
            "is_primary": False,
        },
    )
    assert second.status_code == 200, second.text
    catalog = await client.post(
        f"/api/v1/business/offers/{offer_id}/destinations",
        json={
            "title": "Смартфоны",
            "url": "https://phones.example.com/catalog.html?category=smartphones",
            "type": "CATEGORY",
        },
    )
    assert catalog.status_code == 200, catalog.text
    partner = await partner_with_access(offer_id, "multi-partner@example.com")
    other = await partner_with_access(offer_id, "multi-partner-2@example.com", "Second")

    first_page = (await _pages(client, offer_id))["items"][0]
    links = []
    for index in range(5):
        created = await partner.post(
            "/api/v1/partner/links",
            json={
                "offer_id": offer_id,
                "offer_destination_id": first_page["id"],
                "name": f"Nova {index}",
                "traffic_source": "telegram",
                "destination_url": "https://evil.example/phish",
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["destination_url"] == first_page["url"]
        links.append(created.json())
    assert len({item["short_code"] for item in links}) == 5

    second_link = await partner.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": second.json()["id"],
            "name": "Pulse",
            "traffic_source": "seo",
            "without_campaign": True,
        },
    )
    assert second_link.status_code == 200, second_link.text
    assert second_link.json()["campaign_id"] is None
    assert second_link.json()["destination_url"].endswith("id=pulse-se")

    foreign = await other.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": catalog.json()["id"],
            "name": "Catalog",
            "traffic_source": "seo",
        },
    )
    assert foreign.status_code == 200, foreign.text
    own_codes = {item["short_code"] for item in (await partner.get("/api/v1/partner/links")).json()["items"]}
    assert foreign.json()["short_code"] not in own_codes
    assert all(item["offer_destination_id"] for item in (await partner.get("/api/v1/partner/links")).json()["items"])


@pytest.mark.asyncio
async def test_destination_guards_and_snapshot(client: AsyncClient):
    offer_id = await _business_offer(client, "guard-business@example.com")
    other_offer = await client.post("/api/v1/business/offers", json=_offer_body(name="Другой", product_url="https://phones.example.com/other"))
    assert other_offer.status_code == 200, other_offer.text
    other_page = (await _pages(client, other_offer.json()["id"]))["items"][0]
    page = (await _pages(client, offer_id))["items"][0]
    partner = await partner_with_access(offer_id, "guard-partner@example.com")

    mismatch = await partner.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": other_page["id"],
            "name": "Чужая",
            "traffic_source": "seo",
        },
    )
    assert mismatch.status_code == 404

    unsafe = await client.post(
        f"/api/v1/business/offers/{offer_id}/destinations",
        json={"title": "Bad", "url": "javascript:alert(1)", "type": "LANDING"},
    )
    assert unsafe.status_code == 400
    private = await client.post(
        f"/api/v1/business/offers/{offer_id}/destinations",
        json={"title": "Local", "url": "https://127.0.0.1/admin", "type": "LANDING"},
    )
    assert private.status_code == 400
    duplicate = await client.post(
        f"/api/v1/business/offers/{offer_id}/destinations",
        json={"title": "Копия", "url": page["url"], "type": "PRODUCT"},
    )
    assert duplicate.status_code == 409

    link = await create_partner_link(partner, offer_id, name="Snapshot")
    updated = await client.patch(
        f"/api/v1/business/offers/{offer_id}/destinations/{page['id']}",
        json={"url": "https://phones.example.com/product.html?id=nova-x1"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["snapshots_unchanged"] is True
    assert updated.json()["warning"]
    listed = await partner.get("/api/v1/partner/links")
    stored = next(item for item in listed.json()["items"] if item["id"] == link["id"])
    assert stored["destination_url"] == page["url"]
    assert stored["destination_url"] != updated.json()["url"]

    fresh = await partner.post(
        "/api/v1/partner/links",
        json={"offer_id": offer_id, "name": "Новая", "traffic_source": "seo"},
    )
    assert fresh.json()["destination_url"] == updated.json()["url"]


@pytest.mark.asyncio
async def test_disabled_destination_blocks_new_clicks_and_keeps_history(client: AsyncClient):
    offer_id = await _business_offer(client, "block-business@example.com")
    page = (await _pages(client, offer_id))["items"][0]
    partner = await partner_with_access(offer_id, "block-partner@example.com")
    legacy = await create_partner_link(
        partner,
        offer_id,
        name="Legacy",
        destination_url="https://phones.example.com/product.html?id=legacy",
    )
    bound = await partner.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": page["id"],
            "name": "Bound",
            "traffic_source": "seo",
        },
    )
    assert bound.status_code == 200, bound.text
    bound_body = bound.json()

    clicked = await client.get(f"/go/{bound_body['short_code']}", follow_redirects=False)
    assert clicked.status_code == 302
    assert "rqcid=" not in clicked.headers["location"]
    async with TestingSessionLocal() as session:
        before = await session.scalar(select(func.count(Click.id)))

    disabled = await client.delete(f"/api/v1/business/offers/{offer_id}/destinations/{page['id']}")
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "disabled"
    still = await partner.get("/api/v1/partner/links")
    stored = next(item for item in still.json()["items"] if item["short_code"] == bound_body["short_code"])
    assert stored["status"] == "ACTIVE"

    blocked = await client.get(f"/go/{bound_body['short_code']}", follow_redirects=False)
    assert blocked.status_code == 404
    legacy_redirect = await client.get(f"/go/{legacy['short_code']}", follow_redirects=False)
    assert legacy_redirect.status_code == 302
    assert legacy_redirect.headers["location"] == legacy["destination_url"]
    async with TestingSessionLocal() as session:
        after = await session.scalar(select(func.count(Click.id)))
        link = (
            await session.execute(select(TrackingLink).where(TrackingLink.short_code == bound_body["short_code"]))
        ).scalar_one()
    assert after == before + 1
    assert link.status == "ACTIVE"
    assert link.destination_url == page["url"]

    refused = await partner.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": page["id"],
            "name": "После отключения",
            "traffic_source": "seo",
        },
    )
    assert refused.status_code == 400

    await partner.patch(f"/api/v1/partner/links/{bound_body['id']}/disable")
    restored = await client.patch(
        f"/api/v1/business/offers/{offer_id}/destinations/{page['id']}",
        json={"status": "active"},
    )
    assert restored.status_code == 200, restored.text
    revived = await partner.get("/api/v1/partner/links")
    stored = next(item for item in revived.json()["items"] if item["short_code"] == bound_body["short_code"])
    assert stored["status"] == "DISABLED"


@pytest.mark.asyncio
async def test_access_compliance_and_primary_uniqueness(client: AsyncClient):
    await register_business(client, "policy-business@example.com")
    approval = await client.post(
        "/api/v1/business/offers",
        json=_offer_body(name="Approval", access_policy="approval", product_url="https://shop.example.com/a"),
    )
    assert approval.status_code == 200, approval.text
    approval_id = approval.json()["id"]
    stranger = await partner_with_access(approval_id, "pending-partner@example.com")
    # approval join stays pending, helper expects 200 only for open. Recreate properly.
    pending = await __import__("tests.helpers", fromlist=["external_partner"]).external_partner(
        "approval-only@example.com"
    )
    joined = await pending.post(f"/api/v1/partner/offers/{approval_id}/join")
    assert joined.status_code == 200
    assert joined.json()["status"] == "pending"
    denied = await pending.post(
        "/api/v1/partner/links",
        json={"offer_id": approval_id, "name": "Рано", "traffic_source": "seo"},
    )
    assert denied.status_code == 403
    visible = await pending.get(f"/api/v1/partner/offers/{approval_id}/destinations")
    assert visible.status_code == 200
    assert visible.json()["total"] == 1

    invite = await client.post(
        "/api/v1/business/offers",
        json=_offer_body(name="Invite", access_policy="invite_only", visibility="private", product_url="https://shop.example.com/b"),
    )
    invite_id = invite.json()["id"]
    hidden = await stranger.get(f"/api/v1/partner/offers/{invite_id}/destinations")
    assert hidden.status_code == 404

    betting = await client.post(
        "/api/v1/business/offers",
        json=_offer_body(name="Betting", category="SPORTSBOOK", product_url="https://book.example.com/line"),
    )
    assert betting.status_code == 200, betting.text
    blocked = await client.post(
        f"/api/v1/business/offers/{betting.json()['id']}/destinations",
        json={"title": "Линия", "url": "https://book.example.com/line2", "type": "LANDING"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "COMPLIANCE_RESTRICTED_REQUIRED"

    casino = await client.post(
        "/api/v1/business/offers",
        json=_offer_body(name="Casino", category="ONLINE_CASINO", product_url="https://casino.example.com/play"),
    )
    assert casino.status_code == 200, casino.text
    gambling_pages = await _pages(client, casino.json()["id"])
    assert gambling_pages["total"] == 0
    assert gambling_pages["legacy_skip_reason"] == "COMPLIANCE_VERTICAL_FORBIDDEN"

    pages = (await _pages(client, approval_id))["items"]
    extra = await client.post(
        f"/api/v1/business/offers/{approval_id}/destinations",
        json={"title": "Вторая", "url": "https://shop.example.com/b", "type": "LANDING", "is_primary": True},
    )
    assert extra.status_code == 200, extra.text
    refreshed = await _pages(client, approval_id)
    primaries = [item for item in refreshed["items"] if item["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == extra.json()["id"]
    assert pages[0]["id"] != extra.json()["id"]

    async with TestingSessionLocal() as session:
        session.add(
            OfferDestination(
                offer_id=approval_id,
                title="Второй primary",
                url="https://shop.example.com/c",
                type="LANDING",
                status="active",
                is_primary=True,
                sort_order=9,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_skips_unsafe_urls(client: AsyncClient):
    offer_id = await _business_offer(
        client,
        "backfill-business@example.com",
        product_url="http://insecure.example.com/old",
        status="draft",
    )
    async with TestingSessionLocal() as session:
        first = await backfill_legacy_destinations(session)
        second = await backfill_legacy_destinations(session)
        await session.commit()
    assert all(item["offer_id"] != offer_id or item["reason"] for item in first["skipped"])
    skipped = next(item for item in first["skipped"] if item["offer_id"] == offer_id)
    assert skipped["reason"] == "DESTINATION_HTTPS_REQUIRED"
    assert second["created"] == 0

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.json()["product_url"] == "http://insecure.example.com/old"


@pytest.mark.asyncio
async def test_business_owned_link_stays_separate(client: AsyncClient):
    offer_id = await _business_offer(client, "owned-business@example.com")
    page = (await _pages(client, offer_id))["items"][0]
    own = await client.post(
        f"/api/v1/business/offers/{offer_id}/links",
        json={"offer_destination_id": page["id"], "name": "Своя"},
    )
    assert own.status_code == 200, own.text
    assert own.json()["owner_type"] == "business"
    assert own.json()["partner_id"] is None
    custom = await client.post(
        f"/api/v1/business/offers/{offer_id}/links",
        json={"destination_url": "https://phones.example.com/promo", "name": "Кастом"},
    )
    assert custom.status_code == 200, custom.text
    assert custom.json()["offer_destination_id"] is None
    partner = await partner_with_access(offer_id, "owned-partner@example.com")
    codes = {item["short_code"] for item in (await partner.get("/api/v1/partner/links")).json()["items"]}
    assert own.json()["short_code"] not in codes


@pytest.mark.asyncio
async def test_foreign_campaign_is_rejected(client: AsyncClient):
    offer_id = await _business_offer(client, "campaign-business@example.com")
    owner = await partner_with_access(offer_id, "campaign-owner@example.com")
    other = await partner_with_access(offer_id, "campaign-other@example.com", "Other")
    campaign = await owner.post(
        "/api/v1/partner/campaigns",
        json={"offer_id": offer_id, "name": "Своя кампания"},
    )
    assert campaign.status_code == 200, campaign.text
    page = (await _pages(client, offer_id))["items"][0]
    stolen = await other.post(
        "/api/v1/partner/links",
        json={
            "offer_id": offer_id,
            "offer_destination_id": page["id"],
            "campaign_id": campaign.json()["id"],
            "name": "Чужая кампания",
            "traffic_source": "seo",
        },
    )
    assert stolen.status_code == 403


@pytest.mark.asyncio
async def test_page_url_validation_keeps_query_string():
    nova = await validate_destination_page_url("https://phones.example.com/product.html?id=nova-max")
    pulse = await validate_destination_page_url("https://phones.example.com/product.html?id=pulse-se")
    assert nova != pulse
    assert "id=nova-max" in nova
    with pytest.raises(Exception):
        await validate_destination_page_url("file:///etc/passwd")
    with pytest.raises(Exception):
        await validate_destination_page_url("https://user:pass@demo-clickstream-001.refiq.ru/a")


@pytest.mark.asyncio
async def test_partner_link_allows_missing_traffic_source_and_repeated_names(client: AsyncClient):
    offer_id = await _business_offer(client, "name-business@example.com")
    page = (await _pages(client, offer_id))["items"][0]
    partner = await partner_with_access(offer_id, "name-partner@example.com")
    payload = {
        "offer_id": offer_id,
        "offer_destination_id": page["id"],
        "name": "Nova Phone X1",
        "without_campaign": True,
    }
    first = await partner.post("/api/v1/partner/links", json=payload)
    second = await partner.post("/api/v1/partner/links", json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["traffic_source"] is None
    assert second.json()["name"] == "Nova Phone X1"
    assert first.json()["short_code"] != second.json()["short_code"]
    assert first.json()["campaign_id"] is None
    async with TestingSessionLocal() as session:
        from app.modules.campaigns.models import Campaign

        campaign_count = await session.scalar(
            select(func.count(Campaign.id)).where(Campaign.offer_id == offer_id, Campaign.partner_id.is_not(None))
        )
    assert campaign_count == 0
    assert first.json()["partner_id"]
    assert first.json()["destination_url"] == page["url"]


def test_migration_036_is_additive():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/036_offer_destinations.py"
    source = path.read_text()
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"upgrade", "downgrade"} <= names
    assert 'revision: str = "036"' in source
    assert 'down_revision: Union[str, None] = "035"' in source
    assert "offer_destinations" in source
    assert "offer_destination_id" in source
    assert "uq_offer_destinations_one_primary" in source
    assert "fk_tracking_links_destination_same_offer" in source
    assert "DROP TABLE tracking_links" not in source
    assert 'op.drop_column("tracking_links", "destination_url")' not in source
