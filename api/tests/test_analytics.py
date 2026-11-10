from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.analytics.chsql import scope_clause
from app.modules.analytics.clickhouse import ClickHouseUnavailable, set_clickhouse
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.analytics.metrics import (
    change_pct,
    coverage_quality,
    epc,
    postgres_click_policy,
    ratio,
)
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.common.date_range import ResolvedDateRange
from tests.conftest import TestingSessionLocal
from tests.helpers import create_partner_link, offer_payload, partner_with_access, register_business


class FakeClickHouse:
    def __init__(self):
        self.error = False
        self.rows: list[dict] = []
        self.queries: list[str] = []

    async def query(self, sql: str, params=None):
        self.queries.append(sql)
        if self.error:
            raise ClickHouseUnavailable("down")
        if "reached" in sql and "engaged" in sql:
            return [{"reached": 1, "engaged": 1}]
        return self.rows


@pytest.fixture(autouse=True)
def clickhouse():
    client = FakeClickHouse()
    set_clickhouse(client)
    yield client
    set_clickhouse(None)


def test_rates_use_null_for_zero_denominator():
    assert ratio(1, 0) is None
    assert ratio(0, 0) is None
    assert epc(Decimal("10"), 0) is None
    assert epc(Decimal("10"), 2) == Decimal("5.00")
    assert change_pct(2, 0) is None
    assert change_pct(2, 1) == Decimal("100.0")
    assert coverage_quality(0, 10) == "unavailable"
    assert coverage_quality(1, 10) == "partial"
    assert coverage_quality(8, 10) == "reliable"
    assert postgres_click_policy(
        needs_intersection=True, clickhouse_ok=False, rqcid_count=None, truncated=False
    ) == "unavailable"
    assert postgres_click_policy(
        needs_intersection=False, clickhouse_ok=False, rqcid_count=None, truncated=False
    ) == "all"


def test_device_filter_is_not_concatenated_into_sql():
    filt = AnalyticsFilters(
        date_range=ResolvedDateRange(
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 2, tzinfo=timezone.utc),
            "UTC",
        ),
        offer_id=None,
        campaign_id=None,
        partner_id=None,
        link_id=None,
        site_id=None,
        traffic_source=None,
        device="x' OR 1=1",
        landing=None,
        utm_source=None,
        utm_campaign=None,
        count_statuses=("pending",),
        commission_statuses=("approved",),
        statuses_explicit=False,
    )
    where, params = scope_clause(
        role="business",
        business_id=5,
        partner_id=None,
        filt=filt,
        start=filt.date_range.start,
        end=filt.date_range.end,
    )
    assert "{device:String}" in where
    assert "OR 1=1" not in where
    assert params["device"] == "x' OR 1=1"


async def _offer(client, email: str):
    await register_business(client, email)
    created = await client.post(
        "/api/v1/business/offers",
        json=offer_payload(
            name="Аналитика",
            status="active",
            product_url="https://shop.example.com/item",
            allowed_traffic=["EMAIL"],
        ),
    )
    assert created.status_code == 200, created.text
    return created.json()["id"]


async def _seed(offer_id: int, link_id: int, rqcid: str, status: str, commission: str, when: datetime):
    async with TestingSessionLocal() as session:
        offer = await session.get(Offer, offer_id)
        link = await session.get(TrackingLink, link_id)
        session.add(Click(tracking_link_id=link_id, rqcid=rqcid, created_at=when))
        session.add(
            Conversion(
                business_id=offer.business_id,
                offer_id=offer_id,
                partner_id=link.partner_id,
                tracking_link_id=link_id,
                click_id=rqcid,
                amount=Decimal("100.00"),
                commission_amount=Decimal(commission),
                currency="RUB",
                status=status,
                created_at=when,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_business_metrics_and_partner_isolation(client):
    offer_id = await _offer(client, "analytics-biz@example.com")
    partner = await partner_with_access(offer_id, "analytics-partner@example.com", "North")
    other = await partner_with_access(offer_id, "analytics-other@example.com", "South")
    first = await create_partner_link(partner, offer_id, name="Почта", traffic_source="EMAIL")
    second = await create_partner_link(other, offer_id, name="Вторая", traffic_source="EMAIL")
    current = datetime(2026, 10, 10, tzinfo=timezone.utc)
    previous = datetime(2026, 9, 20, tzinfo=timezone.utc)
    await _seed(offer_id, first["id"], "abc123xyz789", "approved", "10.00", current)
    await _seed(offer_id, first["id"], "abc123xyz788", "pending", "5.00", current)
    await _seed(offer_id, second["id"], "abc123xyz787", "rejected", "99.00", current)
    await _seed(offer_id, first["id"], "abc123xyz786", "approved", "1.00", previous)

    params = {
        "from": "2026-10-01T00:00:00+00:00",
        "to": "2026-10-20T00:00:00+00:00",
        "timezone": "UTC",
    }
    overview = await client.get("/api/v1/analytics/overview", params=params)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["kpis"]["clicks"]["value"] == "3"
    assert body["kpis"]["conversions"]["value"] == "2"
    assert body["kpis"]["cr"]["value"] == "66.67"
    assert body["kpis"]["commission"]["value"] == "10.00"
    assert body["kpis"]["commission"]["currency"] == "RUB"
    assert body["kpis"]["epc"]["value"] == "3.33"
    assert body["kpis"]["clicks"]["change_pct"] == "200.0"
    assert body["sources"]
    assert all(item["label"] != "Яндекс" for item in body["sources"])
    assert body["offers"][0]["href"].endswith(f"/offers/{offer_id}")
    assert "analytics-partner@example.com" not in overview.text

    own = await partner.get("/api/v1/analytics/overview", params=params)
    assert own.status_code == 200, own.text
    assert own.json()["kpis"]["clicks"]["value"] == "2"
    assert own.json()["kpis"]["conversions"]["value"] == "2"
    assert own.json()["efficiency"]["dimension"] == "links"
    assert "analytics-partner@example.com" not in overview.text
    foreign = await partner.get("/api/v1/analytics/overview", params={**params, "offer_id": 999999})
    assert foreign.status_code == 403

    from httpx import ASGITransport, AsyncClient
    from tests.conftest import fastapi_app

    stranger = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")
    await register_business(stranger, "analytics-stranger@example.com")
    denied = await stranger.get("/api/v1/analytics/overview", params={**params, "offer_id": offer_id})
    assert denied.status_code == 403
    hidden = await stranger.get("/api/v1/analytics/overview", params=params)
    assert hidden.status_code == 200
    assert hidden.json()["kpis"]["clicks"]["value"] == "0"
    await stranger.aclose()


@pytest.mark.asyncio
async def test_empty_period_and_clickhouse_failure_stay_contained(client, clickhouse):
    await register_business(client, "analytics-empty@example.com")
    params = {"from": "2026-10-01T00:00:00+00:00", "to": "2026-10-02T00:00:00+00:00", "timezone": "UTC"}
    empty = await client.get("/api/v1/analytics/overview", params=params)
    assert empty.status_code == 200, empty.text
    assert empty.json()["kpis"]["clicks"]["value"] == "0"
    assert empty.json()["kpis"]["cr"]["value"] is None
    assert empty.json()["kpis"]["epc"]["value"] is None

    clickhouse.error = True
    behavior = await client.get("/api/v1/analytics/behavior", params=params)
    assert behavior.status_code == 200, behavior.text
    payload = behavior.json()
    assert payload["meta"]["clickhouse"] == "unavailable"
    assert payload["kpis"]["sessions"]["value"] is None
    assert payload["kpis"]["sessions"]["quality"] == "unavailable"
    health = await client.get("/health")
    assert health.status_code == 200
    from httpx import ASGITransport, AsyncClient
    from tests.conftest import fastapi_app

    guest = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")
    denied = await guest.get("/api/v1/analytics/overview", params=params)
    assert denied.status_code == 401
    await guest.aclose()
