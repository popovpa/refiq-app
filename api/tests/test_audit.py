from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.context import AuditContext
from app.modules.audit.diff import field_changes
from app.modules.audit.events import ActorType, EntityType, OfferEventType
from app.modules.audit.models import AuditEvent
from app.modules.audit.sanitizer import sanitize_payload
from app.modules.audit.service import audit_service
from app.modules.offers.audit import classify_offer_changes, record_offer_mutations, snapshot_offer
from app.modules.offers.models import Offer
from app.modules.products.models import Product
from tests.conftest import TestingSessionLocal
from tests.helpers import offer_payload, register_business
from tests.test_admin import _login


async def _offer_events(offer_id: int) -> list[AuditEvent]:
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(AuditEvent)
            .where(AuditEvent.entity_type == EntityType.OFFER, AuditEvent.entity_id == offer_id)
            .order_by(AuditEvent.id.asc())
        )
        return list(result.scalars().all())


async def _create_offer(client: AsyncClient, **overrides) -> dict:
    await register_business(client, overrides.pop("email", "audit-offer@example.com"))
    created = await client.post("/api/v1/business/offers", json=offer_payload(**overrides))
    assert created.status_code == 200, created.text
    return created.json()


@pytest.mark.asyncio
async def test_audit_service_records_without_independent_commit(db: AsyncSession):
    context = AuditContext(
        actor_type=ActorType.USER,
        source_service="api",
        user_id=11,
        business_id=22,
        request_id="req-audit-1",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    event = await audit_service.record(
        db,
        event_type=OfferEventType.CREATED,
        entity_type=EntityType.OFFER,
        entity_id=101,
        context=context,
        changes={"status": {"before": None, "after": "draft"}, "token": {"before": None, "after": "secret"}},
        metadata={"business_id": 22, "api_key": "plain-secret", "password": "p"},
        source_operation="offers.create",
    )
    assert event.schema_version == 1
    assert event.actor_user_id == 11
    assert event.request_id == "req-audit-1"
    assert event.changes["status"]["after"] == "draft"
    assert event.changes["token"] == "[redacted]"
    assert event.metadata_["business_id"] == 22
    assert event.metadata_["api_key"] == "[redacted]"
    assert event.metadata_["password"] == "[redacted]"

    async with TestingSessionLocal() as other:
        hidden = (
            await other.execute(select(AuditEvent).where(AuditEvent.id == event.id))
        ).scalar_one_or_none()
        assert hidden is None

    await db.commit()

    async with TestingSessionLocal() as other:
        stored = (await other.execute(select(AuditEvent).where(AuditEvent.id == event.id))).scalar_one()
        assert stored.schema_version == 1
        assert stored.request_id == "req-audit-1"
        assert stored.actor_type == ActorType.USER


@pytest.mark.asyncio
async def test_sanitizer_redacts_secret_keys():
    cleaned = sanitize_payload(
        {
            "token": "abc",
            "secret": "s",
            "password": "p",
            "api_key": "k",
            "refresh_token": "r",
            "hold_period_days": {"before": 7, "after": 14},
        }
    )
    assert cleaned["token"] == "[redacted]"
    assert cleaned["secret"] == "[redacted]"
    assert cleaned["password"] == "[redacted]"
    assert cleaned["api_key"] == "[redacted]"
    assert cleaned["refresh_token"] == "[redacted]"
    assert cleaned["hold_period_days"]["before"] == 7
    assert cleaned["hold_period_days"]["after"] == 14


def test_field_diff_skips_noop_values():
    changes = field_changes(
        {"status": "active", "name": "A"},
        {"status": "active", "name": "B"},
        ("status", "name"),
    )
    assert "status" not in changes
    assert changes["name"] == {"before": "A", "after": "B"}


def test_classify_offer_traffic_and_product_blocks():
    before = {
        "geo": "RU",
        "allowed_traffic": ["email"],
        "forbidden_traffic": [],
        "product_id": 1,
        "name": "A",
        "status": "draft",
        "hold_period_days": 7,
        "access_policy": "open",
        "visibility": "public",
        "description": "x",
        "image_url": None,
        "partner_notes": None,
        "materials": [],
        "business_id": 1,
        "category": "SaaS",
        "category_id": 1,
        "conversion_type": "sale",
        "attribution_window_days": 30,
        "currency": "RUB",
        "terms_version": 1,
    }
    after = {
        **before,
        "geo": "KZ",
        "allowed_traffic": ["telegram"],
        "forbidden_traffic": ["cpc"],
        "product_id": 2,
    }
    events = dict(classify_offer_changes(before, after))
    assert OfferEventType.TRAFFIC_POLICY_CHANGED in events
    assert set(events[OfferEventType.TRAFFIC_POLICY_CHANGED]) == {
        "geo",
        "allowed_traffic",
        "forbidden_traffic",
    }
    assert events[OfferEventType.PRODUCT_CHANGED]["product_id"] == {"before": 1, "after": 2}
    assert OfferEventType.UPDATED not in events


@pytest.mark.asyncio
async def test_offer_create_writes_offer_created(client: AsyncClient):
    body = await _create_offer(
        client,
        name="Audited offer",
        hold_period_days=7,
        status="draft",
        access_policy="open",
        visibility="public",
    )
    events = await _offer_events(body["id"])
    assert len(events) == 1
    event = events[0]
    assert event.event_type == OfferEventType.CREATED
    assert event.schema_version == 1
    assert event.entity_type == EntityType.OFFER
    assert event.entity_id == body["id"]
    assert event.actor_type == ActorType.USER
    assert event.actor_user_id is not None
    assert event.actor_business_id is not None
    assert event.request_id
    assert event.source_service == "api"
    assert event.source_operation == "offers.create"
    assert event.changes["status"] == {"before": None, "after": "draft"}
    assert event.changes["hold_period_days"] == {"before": None, "after": 7}
    assert event.changes["product_id"]["after"] is not None
    assert isinstance(event.changes["product_id"]["after"], int)
    assert "description" not in event.changes
    assert "materials" not in event.changes
    assert event.metadata_["business_id"] == event.actor_business_id


@pytest.mark.asyncio
async def test_offer_status_change_is_specialized(client: AsyncClient):
    body = await _create_offer(client, email="audit-status@example.com", status="draft")
    patched = await client.patch(f"/api/v1/business/offers/{body['id']}", json={"status": "active"})
    assert patched.status_code == 200, patched.text
    types = [event.event_type for event in await _offer_events(body["id"])]
    assert types == [OfferEventType.CREATED, OfferEventType.STATUS_CHANGED]
    status_event = (await _offer_events(body["id"]))[-1]
    assert status_event.changes["status"] == {"before": "draft", "after": "active"}
    assert status_event.source_operation == "offers.update"


@pytest.mark.asyncio
async def test_offer_hold_change(client: AsyncClient):
    body = await _create_offer(client, email="audit-hold@example.com", hold_period_days=7)
    patched = await client.patch(f"/api/v1/business/offers/{body['id']}", json={"hold_period_days": 14})
    assert patched.status_code == 200, patched.text
    event = (await _offer_events(body["id"]))[-1]
    assert event.event_type == OfferEventType.HOLD_CHANGED
    assert event.changes["hold_period_days"] == {"before": 7, "after": 14}


@pytest.mark.asyncio
async def test_offer_traffic_policy_change(client: AsyncClient):
    body = await _create_offer(
        client,
        email="audit-traffic@example.com",
        geo="RU",
        allowed_traffic=["EMAIL"],
    )
    patched = await client.patch(
        f"/api/v1/business/offers/{body['id']}",
        json={"geo": "KZ", "allowed_traffic": ["SEO"], "forbidden_traffic": ["SEARCH_ADS"]},
    )
    assert patched.status_code == 200, patched.text
    event = (await _offer_events(body["id"]))[-1]
    assert event.event_type == OfferEventType.TRAFFIC_POLICY_CHANGED
    assert event.changes["geo"]["before"] == "RU"
    assert event.changes["geo"]["after"] == "KZ"
    assert event.changes["allowed_traffic"]["after"] == ["SEO"]


@pytest.mark.asyncio
async def test_offer_access_policy_change(client: AsyncClient):
    body = await _create_offer(client, email="audit-access@example.com", access_policy="open")
    patched = await client.patch(
        f"/api/v1/business/offers/{body['id']}",
        json={"access_policy": "approval", "visibility": "private"},
    )
    assert patched.status_code == 200, patched.text
    event = (await _offer_events(body["id"]))[-1]
    assert event.event_type == OfferEventType.ACCESS_POLICY_CHANGED
    assert event.changes["access_policy"] == {"before": "open", "after": "approval"}
    assert event.changes["visibility"] == {"before": "public", "after": "private"}


@pytest.mark.asyncio
async def test_offer_product_change_records_specialized_event(client: AsyncClient):
    body = await _create_offer(client, email="audit-product@example.com")
    async with TestingSessionLocal() as session:
        offer = await session.get(Offer, body["id"])
        before = snapshot_offer(offer)
        product = Product(
            business_id=offer.business_id,
            name="Replacement product",
            url="https://other.example.com",
            status="active",
        )
        session.add(product)
        await session.flush()
        offer.product_id = product.id
        await record_offer_mutations(
            session,
            offer,
            before,
            snapshot_offer(offer),
            AuditContext(
                actor_type=ActorType.USER,
                source_service="api",
                user_id=1,
                business_id=offer.business_id,
                request_id="product-change",
            ),
            source_operation="offers.update",
        )
        await session.commit()
        new_product_id = product.id

    event = (await _offer_events(body["id"]))[-1]
    assert event.event_type == OfferEventType.PRODUCT_CHANGED
    assert event.changes["product_id"]["after"] == new_product_id
    assert event.changes["product_id"]["before"] != new_product_id


@pytest.mark.asyncio
async def test_offer_ordinary_content_update(client: AsyncClient):
    body = await _create_offer(
        client,
        email="audit-content@example.com",
        name="Old name",
        description="Партнёрское предложение",
        partner_notes="Старые заметки",
    )
    patched = await client.patch(
        f"/api/v1/business/offers/{body['id']}",
        json={
            "name": "New name",
            "description": "Новое описание достаточно длинное",
            "partner_notes": "Новые заметки",
        },
    )
    assert patched.status_code == 200, patched.text
    event = (await _offer_events(body["id"]))[-1]
    assert event.event_type == OfferEventType.UPDATED
    assert event.changes["name"] == {"before": "Old name", "after": "New name"}
    assert "description" in event.changes
    assert "partner_notes" in event.changes


@pytest.mark.asyncio
async def test_offer_noop_patch_does_not_create_audit_event(client: AsyncClient):
    body = await _create_offer(client, email="audit-noop@example.com", status="draft", name="Test offer")
    before_count = len(await _offer_events(body["id"]))
    patched = await client.patch(
        f"/api/v1/business/offers/{body['id']}",
        json={"status": "draft", "name": "Test offer"},
    )
    assert patched.status_code == 200, patched.text
    assert len(await _offer_events(body["id"])) == before_count


@pytest.mark.asyncio
async def test_offer_mutation_rolls_back_when_audit_write_fails(client: AsyncClient, monkeypatch):
    body = await _create_offer(client, email="audit-rollback@example.com", status="draft")

    async def boom(*_args, **_kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr("app.modules.offers.audit.audit_service.record", boom)
    with pytest.raises(BaseException, match="audit write failed"):
        await client.patch(f"/api/v1/business/offers/{body['id']}", json={"status": "active"})

    async with TestingSessionLocal() as session:
        offer = await session.get(Offer, body["id"])
        assert offer.status == "draft"
        status_events = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.entity_id == body["id"],
                AuditEvent.event_type == OfferEventType.STATUS_CHANGED,
            )
        )
        assert status_events == 0


@pytest.mark.asyncio
async def test_admin_can_read_canonical_offer_events(client: AsyncClient, admin_client: AsyncClient):
    body = await _create_offer(client, email="audit-admin-read@example.com")
    await client.patch(f"/api/v1/business/offers/{body['id']}", json={"status": "active"})
    await _login(admin_client, email="audit-reader@refiq.ru")

    listed = await admin_client.get(
        "/api/admin/v1/audit/events",
        params={"entity_type": "OFFER", "entity_id": body["id"]},
    )
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    types = [item["event_type"] for item in payload["items"]]
    assert OfferEventType.CREATED in types
    assert OfferEventType.STATUS_CHANGED in types
    assert all(item["entity_id"] == body["id"] for item in payload["items"])
    assert payload["items"][0]["created_at"] >= payload["items"][-1]["created_at"]

    filtered = await admin_client.get(
        "/api/admin/v1/audit/events",
        params={"event_type": OfferEventType.STATUS_CHANGED, "entity_type": "OFFER"},
    )
    assert filtered.status_code == 200
    assert all(item["event_type"] == OfferEventType.STATUS_CHANGED for item in filtered.json()["items"])

    business_id = payload["items"][0]["actor_business_id"]
    by_business = await admin_client.get("/api/admin/v1/audit/events", params={"business_id": business_id})
    assert by_business.status_code == 200
    assert all(
        item["actor_business_id"] == business_id or (item.get("metadata") or {}).get("business_id") == business_id
        for item in by_business.json()["items"]
    )

    since = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    dated = await admin_client.get("/api/admin/v1/audit/events", params={"date_from": since, "actor_type": "USER"})
    assert dated.status_code == 200
    assert dated.json()["items"]

    legacy = await admin_client.get("/api/admin/v1/audit")
    assert legacy.status_code == 200
    assert "items" in legacy.json()
