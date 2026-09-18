import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.businesses.models import BusinessMembership
from app.modules.notifications.enums import NotificationSeverity, NotificationType
from app.modules.notifications.registry import default_destination, default_title
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from tests.helpers import register_business


async def _user_id(db: AsyncSession, email: str) -> int:
    return (await db.execute(select(User.id).where(User.email == email.lower()))).scalar_one()


@pytest.mark.asyncio
async def test_notification_service_create_and_read_flow(client: AsyncClient, db: AsyncSession):
    await register_business(client, "notify-biz@example.com")
    user_id = await _user_id(db, "notify-biz@example.com")
    business_id = (
        await db.execute(select(BusinessMembership.business_id).where(BusinessMembership.user_id == user_id))
    ).scalar_one()
    service = NotificationService(db)

    created = await service.create(
        user_id=user_id,
        type=NotificationType.SDK_CONNECTED,
        message="shop.example.ru",
        metadata={"site_id": 7, "domain": "shop.example.ru"},
        role_context="business",
        business_id=business_id,
        dedupe_key="sdk_connected:7",
    )
    assert created is not None
    assert created.title == "SDK успешно подключён"
    assert created.severity == NotificationSeverity.SUCCESS.value
    assert created.is_read is False
    assert created.destination == "/business/settings?tab=sites&site=7"

    duplicate = await service.create(
        user_id=user_id,
        type=NotificationType.SDK_CONNECTED,
        role_context="business",
        business_id=business_id,
        dedupe_key="sdk_connected:7",
    )
    assert duplicate is None
    await db.commit()

    unread = await service.unread_count(user_id, role_context="business", business_id=1, partner_id=None)
    assert unread == 1

    listed = await client.get("/api/v1/notifications?limit=20")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "SDK_CONNECTED"
    assert items[0]["is_read"] is False

    count = await client.get("/api/v1/notifications/unread-count")
    assert count.status_code == 200
    assert count.json()["unread_count"] == 1

    marked = await client.post(f"/api/v1/notifications/{items[0]['id']}/read")
    assert marked.status_code == 200
    assert marked.json()["notification"]["is_read"] is True
    assert marked.json()["unread_count"] == 0

    still = await client.get("/api/v1/notifications")
    assert still.json()["items"][0]["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read_keeps_notifications(client: AsyncClient, db: AsyncSession):
    await register_business(client, "notify-all@example.com")
    user_id = await _user_id(db, "notify-all@example.com")
    service = NotificationService(db)
    await service.create(user_id=user_id, type=NotificationType.POSTBACK_FAILED, message="INVALID_AMOUNT")
    await service.create(user_id=user_id, type=NotificationType.SITE_DOMAIN_VERIFIED, message="example.ru")
    await db.commit()

    unread = await client.get("/api/v1/notifications/unread-count")
    assert unread.json()["unread_count"] == 2

    result = await client.post("/api/v1/notifications/read-all")
    assert result.status_code == 200
    assert result.json()["unread_count"] == 0

    listed = await client.get("/api/v1/notifications")
    items = listed.json()["items"]
    assert len(items) == 2
    assert all(item["is_read"] for item in items)


def test_registry_covers_required_types():
    for value in NotificationType:
        assert default_title(value)
        dest = default_destination(value, {"site_id": 3})
        assert dest
        if "POSTBACK" in value:
            assert "integrations" in dest
        elif "PAYOUT" in value or value == NotificationType.PARTNER_TRAFFIC_SUSPENDED:
            assert "payouts" in dest
        else:
            assert "sites" in dest
