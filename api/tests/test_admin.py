import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.service import AdminAuthService
from app.modules.links.models import Click
from sqlalchemy import select
from tests.conftest import TestingSessionLocal
from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


ADMIN_PASSWORD = "admin-pass-word-1"


async def _create_admin(email: str = "ops@refiq.ru", role: str = "super"):
    async with TestingSessionLocal() as session:
        admin = await AdminAuthService(session).create(email, ADMIN_PASSWORD, role)
        await session.commit()
        return admin


async def _login(admin_client: AsyncClient, email: str = "ops@refiq.ru", role: str = "super"):
    await _create_admin(email, role)
    response = await admin_client.post(
        "/api/admin/v1/auth/login",
        json={"email": email, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response


@pytest.mark.asyncio
async def test_public_api_does_not_expose_admin_routes(client: AsyncClient):
    response = await client.get("/api/admin/v1/overview")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_auth_and_session(admin_client: AsyncClient):
    denied = await admin_client.get("/api/admin/v1/overview")
    assert denied.status_code == 401

    login = await _login(admin_client)
    assert login.json()["email"] == "ops@refiq.ru"
    assert "ADMIN_SUPER" in login.json()["permissions"]

    me = await admin_client.get("/api/admin/v1/auth/session")
    assert me.status_code == 200
    assert me.json()["email"] == "ops@refiq.ru"

    overview = await admin_client.get("/api/admin/v1/overview")
    assert overview.status_code == 200
    assert "counts" in overview.json()
    assert "health" in overview.json()


@pytest.mark.asyncio
async def test_admin_permission_checks(admin_client: AsyncClient):
    await _login(admin_client, email="finance@refiq.ru", role="finance")
    blocked = await admin_client.post(
        "/api/admin/v1/businesses/1/suspend",
        json={"reason": "test"},
    )
    assert blocked.status_code == 403

    commissions = await admin_client.get("/api/admin/v1/commissions")
    assert commissions.status_code == 200


@pytest.mark.asyncio
async def test_search_exact_rqcid_and_short_code(client: AsyncClient, admin_client: AsyncClient, db: AsyncSession):
    await register_business(client, "admin-search@example.com")
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="CRM Pro",
            product_url="https://crmpro.example.com/pricing",
            status="active",
            access_policy="open",
            visibility="public",
            commission_type="percent",
            commission_value=10,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert offer.status_code == 200
    offer_id = offer.json()["id"]
    partner = await partner_with_access(offer_id, "admin-search-partner@example.com", "Search Partner")
    created_link = await create_partner_link(partner, offer_id)
    short_code = created_link["short_code"]
    redirected = await client.get(f"/go/{short_code}", follow_redirects=False)
    assert redirected.status_code == 302
    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    assert click is not None

    await _login(admin_client, email="search-admin@refiq.ru")
    by_code = await admin_client.get("/api/admin/v1/search", params={"q": short_code})
    assert by_code.status_code == 200
    types = {item["type"] for item in by_code.json()["items"]}
    assert "tracking_link" in types

    by_rqcid = await admin_client.get("/api/admin/v1/search", params={"q": click.rqcid})
    assert by_rqcid.status_code == 200
    assert any(item.get("primary_action") == "open_trace" for item in by_rqcid.json()["items"])

    trace = await admin_client.get(f"/api/admin/v1/trace/{click.rqcid}")
    assert trace.status_code == 200
    body = trace.json()
    assert body["rqcid"] == click.rqcid
    assert body["summary"]["traffic"] == "OK"
    assert body["timeline"]["tracking"][0]["status"] == "ok"


@pytest.mark.asyncio
async def test_business_list_filters_and_actions(client: AsyncClient, admin_client: AsyncClient):
    await register_business(client, "admin-biz@example.com", name="Acme Admin")
    await _login(admin_client, email="biz-admin@refiq.ru")
    listed = await admin_client.get("/api/admin/v1/businesses", params={"q": "Acme Admin"})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    business_id = listed.json()["items"][0]["id"]

    missing_reason = await admin_client.post(f"/api/admin/v1/businesses/{business_id}/suspend", json={"reason": ""})
    assert missing_reason.status_code == 422

    suspended = await admin_client.post(
        f"/api/admin/v1/businesses/{business_id}/suspend",
        json={"reason": "Chargeback investigation"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    audit = await admin_client.get("/api/admin/v1/audit")
    assert audit.status_code == 200
    assert any(item["action"] == "SUSPEND_BUSINESS" for item in audit.json()["items"])

    activated = await admin_client.post(
        f"/api/admin/v1/businesses/{business_id}/activate",
        json={"reason": "Issue resolved"},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"


@pytest.mark.asyncio
async def test_clicks_pagination_and_postback_attempt(client: AsyncClient, admin_client: AsyncClient, db: AsyncSession):
    await register_business(client, "admin-pb@example.com")
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="CRM Pro",
            product_url="https://crmpro.example.com/pricing",
            status="active",
            access_policy="open",
            visibility="public",
            commission_type="percent",
            commission_value=10,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    offer_id = offer.json()["id"]
    partner = await partner_with_access(offer_id, "admin-pb-partner@example.com", "PB Partner")
    created = await create_partner_link(partner, offer_id, name="Ads")
    short_code = created["short_code"]
    await client.get(f"/go/{short_code}", follow_redirects=False)
    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    token = await client.post("/api/v1/business/postback/credential")
    assert token.status_code == 200
    await client.post(
        "/postback",
        json={"rqcid": click.rqcid, "amount": 1000},
        headers={"Authorization": f"Bearer {token.json()['token']}"},
    )

    await _login(admin_client, email="pb-admin@refiq.ru")
    clicks = await admin_client.get("/api/admin/v1/clicks")
    assert clicks.status_code == 200
    assert "next_cursor" in clicks.json()
    assert any(item["rqcid"] == click.rqcid for item in clicks.json()["items"])

    postbacks = await admin_client.get("/api/admin/v1/postbacks")
    assert postbacks.status_code == 200
    assert any(item["rqcid"] == click.rqcid and item["result"] == "ACCEPTED" for item in postbacks.json()["items"])

    public = await client.post(
        "/postback",
        json={"rqcid": "abcdefghijkl"},
        headers={"Authorization": "Bearer rqpb_not-a-real-token"},
    )
    assert public.status_code == 401
    postbacks = await admin_client.get("/api/admin/v1/postbacks")
    assert any(item["reason_code"] == "INVALID_TOKEN" for item in postbacks.json()["items"])


@pytest.mark.asyncio
async def test_inactive_offer_blocks_link_activation(client: AsyncClient, admin_client: AsyncClient):
    await register_business(client, "admin-link@example.com")
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Paused Offer",
            product_url="https://crmpro.example.com/pricing",
            status="active",
            access_policy="open",
            visibility="public",
            commission_type="percent",
            commission_value=10,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    offer_id = offer.json()["id"]
    partner = await partner_with_access(offer_id, "admin-link-partner@example.com", "Link Partner")
    created = await create_partner_link(partner, offer_id, name="Ads")
    link_id = created["id"]

    await _login(admin_client, email="link-admin@refiq.ru")
    await admin_client.post(f"/api/admin/v1/offers/{offer_id}/pause", json={"reason": "Broken landing"})
    paused = await admin_client.post(f"/api/admin/v1/tracking-links/{link_id}/pause", json={"reason": "Stop traffic"})
    assert paused.status_code == 200
    conflict = await admin_client.post(
        f"/api/admin/v1/tracking-links/{link_id}/activate",
        json={"reason": "Try again"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "OFFER_INACTIVE"


async def _seed_admin_filter_funnel(
    client: AsyncClient,
    db: AsyncSession,
    *,
    email: str,
    name: str,
    site_url: str,
    offer_name: str,
):
    await register_business(client, email, name=name, website=site_url)
    session = await client.get("/api/v1/auth/session")
    assert session.status_code == 200, session.text
    business_id = int(session.json()["active_business_id"])

    site = await client.post("/api/v1/business/sites", json={"url": site_url})
    assert site.status_code == 200, site.text
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name=offer_name,
            product_url=f"{site_url.rstrip('/')}/pricing",
            status="active",
            access_policy="open",
            visibility="public",
            commission_type="percent",
            commission_value=10,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert offer.status_code == 200, offer.text
    offer_id = offer.json()["id"]

    partner = await partner_with_access(offer_id, f"{email}.partner", f"{name} Partner")
    created = await create_partner_link(partner, offer_id, name="Ads")
    redirected = await client.get(f"/go/{created['short_code']}", follow_redirects=False)
    assert redirected.status_code == 302

    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    assert click is not None
    token = await client.post("/api/v1/business/postback/credential")
    assert token.status_code == 200, token.text
    postback = await client.post(
        "/postback",
        json={"rqcid": click.rqcid, "amount": 1000},
        headers={"Authorization": f"Bearer {token.json()['token']}"},
    )
    assert postback.status_code == 200, postback.text

    return {
        "business_id": business_id,
        "business_name": name,
        "site_id": int(site.json()["id"]),
        "offer_id": int(offer_id),
        "link_id": int(created["id"]),
        "rqcid": click.rqcid,
    }


def _item_ids(response, key: str = "id"):
    return {item[key] for item in response.json()["items"]}


@pytest.mark.asyncio
async def test_admin_business_lookup_and_list_filters(
    admin_client: AsyncClient,
    db: AsyncSession,
):
    from httpx import ASGITransport

    from app.main import app as fastapi_app

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as alpha:
        a = await _seed_admin_filter_funnel(
            alpha,
            db,
            email="alpha-filter@example.com",
            name="Zephyr UniqueBiz",
            site_url="https://zephyr-filter.example.com",
            offer_name="Zephyr Offer",
        )
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as beta:
        b = await _seed_admin_filter_funnel(
            beta,
            db,
            email="beta-filter@example.com",
            name="Quasar UniqueBiz",
            site_url="https://quasar-filter.example.com",
            offer_name="Quasar Offer",
        )

    await _login(admin_client, email="filter-admin@refiq.ru")

    lookup = await admin_client.get("/api/admin/v1/businesses/lookup", params={"search": "Zephyr"})
    assert lookup.status_code == 200, lookup.text
    assert lookup.json() == [{"id": a["business_id"], "name": "Zephyr UniqueBiz"}]

    by_id = await admin_client.get("/api/admin/v1/businesses/lookup", params={"id": b["business_id"]})
    assert by_id.status_code == 200
    assert by_id.json() == [{"id": b["business_id"], "name": "Quasar UniqueBiz"}]

    missing = await admin_client.get("/api/admin/v1/businesses/lookup", params={"search": "no-such-business-xyz"})
    assert missing.status_code == 200
    assert missing.json() == []

    compact = await admin_client.get("/api/admin/v1/businesses/lookup")
    assert compact.status_code == 200
    assert {item["id"] for item in compact.json()} >= {a["business_id"], b["business_id"]}
    assert all(set(item) == {"id", "name"} for item in compact.json())

    sites = await admin_client.get("/api/admin/v1/sites", params={"business_id": a["business_id"]})
    assert sites.status_code == 200
    assert _item_ids(sites) == {a["site_id"]}

    offers = await admin_client.get("/api/admin/v1/offers", params={"business_id": a["business_id"]})
    assert offers.status_code == 200
    assert _item_ids(offers) == {a["offer_id"]}

    links = await admin_client.get("/api/admin/v1/tracking-links", params={"business_id": b["business_id"]})
    assert links.status_code == 200
    assert _item_ids(links) == {b["link_id"]}

    clicks = await admin_client.get("/api/admin/v1/clicks", params={"business_id": a["business_id"]})
    assert clicks.status_code == 200
    assert {item["rqcid"] for item in clicks.json()["items"]} == {a["rqcid"]}

    conversions = await admin_client.get(
        "/api/admin/v1/conversions", params={"business_id": b["business_id"]}
    )
    assert conversions.status_code == 200
    assert {item["business_id"] for item in conversions.json()["items"]} == {b["business_id"]}
    assert all(item["rqcid"] == b["rqcid"] for item in conversions.json()["items"])

    postbacks = await admin_client.get("/api/admin/v1/postbacks", params={"business_id": a["business_id"]})
    assert postbacks.status_code == 200
    assert {item["business_id"] for item in postbacks.json()["items"]} == {a["business_id"]}
    assert {item["rqcid"] for item in postbacks.json()["items"]} == {a["rqcid"]}

    all_clicks = await admin_client.get("/api/admin/v1/clicks")
    assert {a["rqcid"], b["rqcid"]} <= {item["rqcid"] for item in all_clicks.json()["items"]}

