import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses.models import Business, BusinessMembership
from tests.helpers import become_partner, offer_payload, register_business, register_user


async def _create_offer(
    client: AsyncClient,
    email: str,
    *,
    access_policy: str = "open",
    status: str = "active",
    visibility: str = "public",
    name: str = "Own CRM",
) -> str:
    await register_business(client, email)
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name=name,
            product_url="https://own.example.com",
            status=status,
            access_policy=access_policy,
            visibility=visibility,
            commission_type="percent",
            commission_value=10,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert offer.status_code == 200, offer.text
    return str(offer.json()["id"])


async def _add_offer(
    client: AsyncClient,
    *,
    access_policy: str = "open",
    status: str = "active",
    visibility: str = "public",
    name: str = "Own CRM",
    commission_value: float = 10,
) -> str:
    offer = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name=name,
            product_url="https://own.example.com",
            status=status,
            access_policy=access_policy,
            visibility=visibility,
            commission_type="percent",
            commission_value=commission_value,
            allowed_traffic=["seo", "telegram"],
        ),
    )
    assert offer.status_code == 200, offer.text
    return str(offer.json()["id"])


@pytest.mark.asyncio
async def test_own_public_offer_visible_in_partner_marketplace(client: AsyncClient):
    offer_id = await _create_offer(client, "own-public@example.com", access_policy="open")
    await become_partner(client, "Owner Partner")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    assert catalog.status_code == 200
    item = next(row for row in catalog.json()["items"] if str(row["id"]) == offer_id)
    assert item["is_own_offer"] is True
    assert item["commission_rules"][0]["value"] == 10

    detail = await client.get(f"/api/v1/partner/offers/{offer_id}")
    assert detail.status_code == 200
    assert detail.json()["is_own_offer"] is True
    assert detail.json()["application"] is None

    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_own_approval_offer_bypasses_partner_access(client: AsyncClient):
    offer_id = await _create_offer(
        client, "own-approval@example.com", access_policy="approval", name="Approval Own"
    )
    await become_partner(client, "Owner Approval")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    item = next(row for row in catalog.json()["items"] if str(row["id"]) == offer_id)
    assert item["is_own_offer"] is True
    assert item["partner_status"] is None

    detail = await client.get(f"/api/v1/partner/offers/{offer_id}")
    assert detail.status_code == 200
    assert detail.json()["is_own_offer"] is True

    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_own_invite_only_offer_visible_without_invitation(client: AsyncClient):
    offer_id = await _create_offer(
        client, "own-invite@example.com", access_policy="invite_only", name="Invite Own"
    )
    await become_partner(client, "Owner Invite")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    item = next(row for row in catalog.json()["items"] if str(row["id"]) == offer_id)
    assert item["is_own_offer"] is True

    detail = await client.get(f"/api/v1/partner/offers/{offer_id}")
    assert detail.status_code == 200
    assert detail.json()["is_own_offer"] is True

    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_own_draft_hidden_paused_visible_archived_hidden(client: AsyncClient):
    draft_id = await _create_offer(client, "own-lifecycle@example.com", status="draft", name="Draft Own")
    await become_partner(client, "Lifecycle Owner")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    assert all(str(row["id"]) != draft_id for row in catalog.json()["items"])
    assert (await client.get(f"/api/v1/partner/offers/{draft_id}")).status_code == 404

    await client.post("/api/v1/me/context", json={"role": "business"})
    paused_id = await _add_offer(client, status="paused", name="Paused Own", commission_value=12)
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    item = next(row for row in catalog.json()["items"] if str(row["id"]) == paused_id)
    assert item["is_own_offer"] is True
    assert item["status"] == "paused"

    await client.post("/api/v1/me/context", json={"role": "business"})
    archived = await client.patch(f"/api/v1/business/offers/{paused_id}", json={"status": "archived"})
    assert archived.status_code == 200
    await client.post("/api/v1/me/context", json={"role": "partner"})
    catalog = await client.get("/api/v1/partner/offers/marketplace")
    assert all(str(row["id"]) != paused_id for row in catalog.json()["items"])


@pytest.mark.asyncio
async def test_external_partner_still_needs_approval(client: AsyncClient):
    offer_id = await _create_offer(
        client, "external-approval-biz@example.com", access_policy="approval", name="External Approval"
    )

    await register_user(client, "external-partner@example.com")
    await become_partner(client, "External Partner")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    catalog = await client.get("/api/v1/partner/offers/marketplace")
    item = next(row for row in catalog.json()["items"] if str(row["id"]) == offer_id)
    assert item["is_own_offer"] is False

    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200
    assert join.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_own_offer_blocks_partner_link_and_uses_business_promotion(client: AsyncClient):
    offer_id = await _create_offer(client, "own-promo@example.com")
    await become_partner(client, "Promo Dual")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    partner_link = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": int(offer_id), "name": "Self", "traffic_source": "telegram"},
    )
    assert partner_link.status_code == 403

    await client.post("/api/v1/me/context", json={"role": "business"})
    created = await client.post(
        f"/api/v1/business/offers/{offer_id}/links",
        json={"destination_url": "https://own.example.com/landing"},
    )
    assert created.status_code == 200
    assert created.json()["owner_type"] == "business"
    assert created.json()["partner_id"] is None


@pytest.mark.asyncio
async def test_cannot_create_business_promotion_for_foreign_offer(client: AsyncClient):
    foreign_id = await _create_offer(client, "foreign-owner@example.com", name="Foreign")
    await register_business(client, "attacker@example.com")
    stolen = await client.post(
        f"/api/v1/business/offers/{foreign_id}/links",
        json={"destination_url": "https://attacker.example.com"},
    )
    assert stolen.status_code == 404


@pytest.mark.asyncio
async def test_context_switch_with_offer_id_selects_owning_business(client: AsyncClient):
    offer_id = await _create_offer(client, "switch-own@example.com")
    first = await client.get("/api/v1/auth/session")
    business_a = first.json()["active_business_id"]
    await become_partner(client, "Switch Owner")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    switched = await client.post("/api/v1/me/context", json={"role": "business", "offer_id": int(offer_id)})
    assert switched.status_code == 200
    assert switched.json()["active_role"] == "business"
    assert switched.json()["active_business_id"] == business_a

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.status_code == 200
    assert str(detail.json()["id"]) == offer_id


@pytest.mark.asyncio
async def test_context_switch_with_offer_id_picks_second_business(client: AsyncClient, db: AsyncSession):
    offer_a = await _create_offer(client, "multi-biz@example.com", name="Offer A")
    session = await client.get("/api/v1/auth/session")
    business_a = session.json()["active_business_id"]
    user_id = int(session.json()["user"]["id"])

    business_b = Business(name="Second Co", country="RU")
    db.add(business_b)
    await db.flush()
    db.add(BusinessMembership(business_id=business_b.id, user_id=user_id, permission_role="owner", status="active"))
    await db.commit()

    switched_b = await client.post(
        "/api/v1/me/context",
        json={"role": "business", "business_id": business_b.id},
    )
    assert switched_b.status_code == 200
    assert switched_b.json()["active_business_id"] == str(business_b.id)
    offer_b = await _add_offer(client, name="Offer B")

    await become_partner(client, "Multi Owner")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    assert (await client.get("/api/v1/auth/session")).json()["active_business_id"] is None

    back = await client.post("/api/v1/me/context", json={"role": "business", "offer_id": int(offer_b)})
    assert back.status_code == 200
    assert back.json()["active_role"] == "business"
    assert back.json()["active_business_id"] == str(business_b.id)
    assert back.json()["active_business_id"] != business_a

    assert (await client.get(f"/api/v1/business/offers/{offer_b}")).status_code == 200
    assert (await client.get(f"/api/v1/business/offers/{offer_a}")).status_code == 404


@pytest.mark.asyncio
async def test_context_switch_rejects_foreign_offer_and_keeps_partner(client: AsyncClient):
    foreign_id = await _create_offer(client, "foreign-switch@example.com", name="Foreign Switch")
    await register_business(client, "other-switch@example.com")
    await become_partner(client, "Other Switch")
    await client.post("/api/v1/me/context", json={"role": "partner"})

    failed = await client.post("/api/v1/me/context", json={"role": "business", "offer_id": int(foreign_id)})
    assert failed.status_code == 403

    session = await client.get("/api/v1/auth/session")
    assert session.json()["active_role"] == "partner"
    assert session.json()["active_business_id"] is None
