import pytest
from httpx import AsyncClient
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import BusinessSettings
from tests.helpers import register_business


@pytest.mark.asyncio
async def test_business_settings_returns_onboarding_company_fields(client: AsyncClient):
    await register_business(client, "settings-biz@example.com")

    response = await client.get("/api/v1/business/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme"
    assert data["website"] == "https://acme.example.com"
    assert data["category"] == "SaaS"
    assert data["work_email"] == "settings-biz@example.com"
    assert data["phone"] == "+79991112233"
    assert data["description"] == "Test company"
    assert data["logo_url"] is None
    assert data["currency"] == "RUB"
    assert data["default_attribution_window_days"] == 30
    assert data["default_access_policy"] == "approval"
    assert "auto_approve_partners" not in data
    assert "default_cookie_days" not in data


@pytest.mark.asyncio
async def test_business_settings_patch_company_and_defaults(client: AsyncClient):
    await register_business(client, "settings-update@example.com")

    company = await client.patch("/api/v1/business/settings", json={
        "name": "Acme Labs",
        "website": "https://acme-labs.example.com",
        "country": "kz",
        "category": "Fintech",
        "work_email": "ops@acme-labs.example.com",
        "phone": "+77001112233",
        "description": "Updated company",
        "logo_url": "data:image/jpeg;base64,abc",
    })
    assert company.status_code == 200

    defaults = await client.patch("/api/v1/business/settings", json={
        "currency": "USD",
        "default_attribution_window_days": 14,
        "default_access_policy": "invite_only",
        "default_confirmation_days": 7,
    })
    assert defaults.status_code == 200

    response = await client.get("/api/v1/business/settings")
    data = response.json()
    assert data["name"] == "Acme Labs"
    assert data["website"] == "https://acme-labs.example.com"
    assert data["country"] == "KZ"
    assert data["category"] == "Fintech"
    assert data["work_email"] == "ops@acme-labs.example.com"
    assert data["phone"] == "+77001112233"
    assert data["description"] == "Updated company"
    assert data["logo_url"] == "data:image/jpeg;base64,abc"
    assert data["currency"] == "USD"
    assert data["default_attribution_window_days"] == 14
    assert data["default_access_policy"] == "invite_only"
    assert data["default_confirmation_days"] == 7


@pytest.mark.asyncio
async def test_business_settings_patch_preserves_unrelated_jsonb_keys(client: AsyncClient, db: AsyncSession):
    await register_business(client, "settings-preserve@example.com")

    session_response = await client.get("/api/v1/auth/session")
    business_id = int(session_response.json()["active_business_id"])

    result = await db.execute(select(BusinessSettings).where(BusinessSettings.business_id == business_id))
    row = result.scalar_one()
    row.settings = {**(row.settings or {}), "verified_domains": ["acme.example.com"]}
    await db.commit()

    updated = await client.patch("/api/v1/business/settings", json={"website": "https://new.example.com"})
    assert updated.status_code == 200

    db.expire_all()
    result = await db.execute(select(BusinessSettings).where(BusinessSettings.business_id == business_id))
    row = result.scalar_one()
    assert row.settings["website"] == "https://new.example.com"
    assert row.settings["verified_domains"] == ["acme.example.com"]
