import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.catalog.data import category_belongs_to_unique_vertical
from app.modules.conversions.models import Conversion
from app.modules.offers.models import Offer
from tests.conftest import TestingSessionLocal
from tests.helpers import offer_payload, register_business


def test_each_category_maps_to_one_vertical():
    mapping = category_belongs_to_unique_vertical()
    assert mapping["ONLINE_COURSES"] == "EDUCATION"
    assert mapping["ANTIVIRUS"] == "CYBERSECURITY"
    assert mapping["CRM"] == "SAAS"
    assert len(mapping) == len(set(mapping))


@pytest.mark.asyncio
async def test_create_offer_requires_allowlist_and_hold(client: AsyncClient):
    await register_business(client, "wizard-model@example.com")
    missing = await client.post("/api/v1/business/offers", json={"name": "No traffic", "status": "draft"})
    assert missing.status_code == 400

    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Python course",
            category="ONLINE_COURSES",
            geo=["RU", "KZ"],
            allowed_traffic=["EMAIL"],
            hold_period_days=7,
        ),
    )
    assert created.status_code == 200
    data = created.json()
    assert data["category"] == "ONLINE_COURSES"
    assert data["vertical_code"] == "EDUCATION"
    assert data["geo"] == "RU,KZ"
    assert data["allowed_traffic"] == ["EMAIL"]
    assert data["forbidden_traffic"] == []
    assert data["hold_period_days"] == 7
    assert "destination_url" not in data


@pytest.mark.asyncio
async def test_empty_allowlist_rejects_all_partner_traffic(client: AsyncClient):
    await register_business(client, "strict-allow@example.com")
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(name="Email only", allowed_traffic=["EMAIL"], status="active", access_policy="open"),
    )
    assert created.status_code == 200

    rejected = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(name="Bad hold", hold_period_days=5),
    )
    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_hold_snapshot_does_not_change_after_offer_update(client: AsyncClient):
    await register_business(client, "hold-snap@example.com")
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(name="Hold offer", hold_period_days=7, status="active", access_policy="open"),
    )
    offer_id = created.json()["id"]
    async with TestingSessionLocal() as session:
        offer = (await session.execute(select(Offer).where(Offer.id == offer_id))).scalar_one()
        conversion = Conversion(
            business_id=offer.business_id,
            offer_id=offer.id,
            amount=1000,
            currency="RUB",
            commission_amount=100,
            status="pending",
            hold_period_days_snapshot=offer.hold_period_days,
        )
        session.add(conversion)
        await session.commit()
        conversion_id = conversion.id

    updated = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"hold_period_days": 30})
    assert updated.status_code == 200

    async with TestingSessionLocal() as session:
        conversion = (await session.execute(select(Conversion).where(Conversion.id == conversion_id))).scalar_one()
        offer = (await session.execute(select(Offer).where(Offer.id == offer_id))).scalar_one()
        assert offer.hold_period_days == 30
        assert conversion.hold_period_days_snapshot == 7


@pytest.mark.asyncio
async def test_offer_description_and_partner_notes_roundtrip(client: AsyncClient):
    await register_business(client, "notes-fields@example.com")
    missing = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(name="No description", description="   "),
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["message"] == "Укажите описание оффера"

    too_long = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(name="Long description", description="а" * 3001),
    )
    assert too_long.status_code == 400
    assert too_long.json()["error"]["message"] == "Максимальная длина — 3000 символов"

    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Python course",
            description="Онлайн-курс Python для начинающих.\nЕсть итоговый проект.",
            partner_notes=None,
            hold_period_days=7,
            status="draft",
        ),
    )
    assert created.status_code == 200
    data = created.json()
    offer_id = data["id"]
    assert data["description"] == "Онлайн-курс Python для начинающих.\nЕсть итоговый проект."
    assert data["partner_notes"] is None
    assert data["hold_period_days"] == 7
    assert data["access_policy"] == "open"

    with_notes = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Python notes",
            description="Курс для начинающих",
            partner_notes="  Лучше аудитория 20–35 лет.\nАкцент на практике.  ",
        ),
    )
    assert with_notes.status_code == 200
    assert with_notes.json()["partner_notes"] == "Лучше аудитория 20–35 лет.\nАкцент на практике."

    detail = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "Онлайн-курс Python для начинающих.\nЕсть итоговый проект."
    assert detail.json()["partner_notes"] is None

    updated = await client.patch(
        f"/api/v1/business/offers/{offer_id}",
        json={
            "description": "Обновлённое описание курса",
            "partner_notes": "Сезонность: набор в сентябре.",
        },
    )
    assert updated.status_code == 200
    after = await client.get(f"/api/v1/business/offers/{offer_id}")
    assert after.json()["description"] == "Обновлённое описание курса"
    assert after.json()["partner_notes"] == "Сезонность: набор в сентябре."
    assert after.json()["hold_period_days"] == 7
    assert after.json()["access_policy"] == "open"
    assert after.json()["name"] == "Python course"

    cleared = await client.patch(f"/api/v1/business/offers/{offer_id}", json={"partner_notes": "   "})
    assert cleared.status_code == 200
    async with TestingSessionLocal() as session:
        offer = (await session.execute(select(Offer).where(Offer.id == offer_id))).scalar_one()
        assert offer.partner_notes is None
        assert offer.description == "Обновлённое описание курса"
        assert offer.hold_period_days == 7

    empty_description = await client.patch(
        f"/api/v1/business/offers/{offer_id}",
        json={"description": "   "},
    )
    assert empty_description.status_code == 400
    assert empty_description.json()["error"]["message"] == "Укажите описание оффера"

    too_long_notes = await client.patch(
        f"/api/v1/business/offers/{offer_id}",
        json={"partner_notes": "б" * 3001},
    )
    assert too_long_notes.status_code == 400
    assert too_long_notes.json()["error"]["message"] == "Максимальная длина — 3000 символов"
