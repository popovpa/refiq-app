import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.links.models import Click
from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


@pytest.mark.asyncio
async def test_business_dashboard_aggregates_period_metrics(client: AsyncClient, db: AsyncSession):
    await register_business(client, "dash-biz@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(
        name="CRM Pro",
        access_policy="open",
        status="active",
        product_url="https://crmpro.example.com/pricing",
        commission_type="percent",
        commission_value=10,
        allowed_traffic=["seo", "telegram"],
    ))
    assert created.status_code == 200
    offer_id = created.json()["id"]

    empty = await client.get("/api/v1/business/dashboard?days=7")
    assert empty.status_code == 200
    payload = empty.json()
    assert payload["kpis"]["active_offers"] == 1
    assert payload["kpis"]["conversions"] == 0
    assert payload["has_offers"] is True
    assert payload["top_offers"] == []
    assert payload["funnel"]["clicks"] == 0
    assert "timeseries" in payload
    assert len(payload["timeseries"]) == 7

    partner = await partner_with_access(offer_id, "dash-partner@example.com", "Dash Partner")
    link = await create_partner_link(partner, offer_id)
    clicked = await client.get(f"/go/{link['short_code']}", follow_redirects=False)
    assert clicked.status_code == 302
    token = (await client.post("/api/v1/business/postback/credential")).json()["token"]
    db.expire_all()
    click = (await db.execute(select(Click).order_by(Click.id.desc()))).scalars().first()
    assert click is not None
    accepted = await client.post(
        "/postback",
        json={"rqcid": click.rqcid, "amount": 1000, "currency": "RUB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200

    dashboard = await client.get("/api/v1/business/dashboard?days=7")
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["kpis"]["conversions"] == 1
    assert data["funnel"]["clicks"] == 1
    assert len(data["top_offers"]) == 1
    assert data["top_offers"][0]["name"] == "CRM Pro"
    assert data["top_offers"][0]["conversions"] == 1
    assert len(data["top_partners"]) == 1
    assert data["recent_conversions"][0]["offer_name"] == "CRM Pro"
    assert data["recent_conversions"][0]["partner_name"]
    assert "id" in data["recent_conversions"][0]
    assert data["integrations"]["postback"] in {"connected", "awaiting_first_request", "not_configured"}
    assert data["integrations"]["sdk"] in {"connected", "awaiting_first_request", "not_configured"}
    assert sum(item["conversions"] for item in data["timeseries"]) == 1
