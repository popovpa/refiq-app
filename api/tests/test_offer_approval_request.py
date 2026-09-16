import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.offers.models import OfferPartnerAccess
from tests.conftest import TestingSessionLocal
from tests.helpers import offer_payload, register_business


async def _external_partner(email: str, display_name: str = "Partner"):
    from tests.helpers import external_partner

    return await external_partner(email, display_name)


@pytest.mark.asyncio
async def test_approval_request_is_partner_offer_only(client: AsyncClient):
    await register_business(client, "approval-compact@example.com")
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Курсы авиации",
            access_policy="approval",
            status="active",
            product_url="https://aviation.example.com",
            allowed_traffic=["seo", "telegram"],
            geo="RU,KZ",
        ),
    )
    assert created.status_code == 200
    offer_id = created.json()["id"]

    partner = await _external_partner("compact-partner@example.com", "Авиа Партнёр")
    try:
        join = await partner.post(
            f"/api/v1/partner/offers/{offer_id}/join",
            json={
                "comment": "Можно писать бизнесу напрямую: user@example.com",
                "business_comment": "hidden",
                "traffic_sources": ["telegram"],
                "planned_traffic": ["seo"],
                "topics": "авиация",
                "geo": "DE",
            },
        )
        assert join.status_code == 200
        assert join.json()["status"] == "pending"

        duplicate = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert duplicate.status_code == 409

        partner_detail = await partner.get(f"/api/v1/partner/offers/{offer_id}")
        assert partner_detail.status_code == 200
        application = partner_detail.json()["application"]
        assert application["status"] == "pending"
        assert application["created_at"]
        assert "comment" not in application
        assert "traffic_sources" not in application
        assert "geo" not in application
        assert partner_detail.json()["partner_status"] == "pending"

        business_detail = await client.get(f"/api/v1/business/offers/{offer_id}")
        pending = business_detail.json()["pending_applications"]
        assert len(pending) == 1
        access_id = pending[0]["id"]
        partner_id = pending[0]["partner_id"]
        assert pending[0]["name"] == "Авиа Партнёр"
        assert pending[0]["status"] == "pending"
        assert pending[0]["created_at"]
        assert "comment" not in pending[0]
        assert "business_comment" not in pending[0]
        assert "traffic_sources" not in pending[0]
        assert "topics" not in pending[0]
        assert "geo" not in pending[0]

        profile = await client.get(f"/api/v1/business/partners/{partner_id}")
        assert profile.status_code == 200
        assert profile.json()["display_name"] == "Авиа Партнёр"
        assert "email" not in profile.json()

        missing_reason = await client.post(f"/api/v1/business/offers/{offer_id}/partners/{access_id}/reject", json={"reason": "   "})
        assert missing_reason.status_code == 400

        reject = await client.post(
            f"/api/v1/business/offers/{offer_id}/partners/{access_id}/reject",
            json={"reason": "Не подходит аудитория"},
        )
        assert reject.status_code == 200

        async with TestingSessionLocal() as session:
            access = (
                await session.execute(select(OfferPartnerAccess).where(OfferPartnerAccess.id == access_id))
            ).scalar_one()
            assert access.status == "rejected"
            assert access.rejection_reason == "Не подходит аудитория"
            assert access.comment is None
            assert access.business_comment is None
            assert access.traffic_sources is None
            assert access.geo is None

        rejected_detail = await partner.get(f"/api/v1/partner/offers/{offer_id}")
        assert rejected_detail.json()["partner_status"] == "rejected"
        assert rejected_detail.json()["rejection_reason"] == "Не подходит аудитория"
        assert rejected_detail.json()["application"]["rejection_reason"] == "Не подходит аудитория"

        reapply = await partner.post(f"/api/v1/partner/offers/{offer_id}/join")
        assert reapply.status_code == 200
        assert reapply.json()["status"] == "pending"

        after = await client.get(f"/api/v1/business/offers/{offer_id}")
        pending_again = after.json()["pending_applications"]
        assert len(pending_again) == 1
        assert pending_again[0]["id"] == access_id
        assert pending_again[0].get("rejection_reason") in {None}

        approve = await client.post(f"/api/v1/business/offers/{offer_id}/partners/{access_id}/approve")
        assert approve.status_code == 200

        seo_link = await partner.post(
            "/api/v1/partner/links",
            json={"offer_id": offer_id, "name": "SEO", "traffic_source": "seo"},
        )
        telegram_link = await partner.post(
            "/api/v1/partner/links",
            json={"offer_id": offer_id, "name": "TG", "traffic_source": "telegram"},
        )
        assert seo_link.status_code == 200
        assert telegram_link.status_code == 200
    finally:
        await partner.aclose()
