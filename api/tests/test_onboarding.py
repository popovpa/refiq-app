import pytest
from httpx import AsyncClient

from tests.helpers import become_business, become_partner, register_user


@pytest.mark.asyncio
async def test_register_has_no_roles(client: AsyncClient):
    response = await register_user(client, "new-user@example.com")
    data = response.json()
    assert data["user"]["roles"] == []
    assert data["active_role"] is None

    forbidden = await client.get("/api/v1/business/dashboard")
    assert forbidden.status_code == 403

    partner_forbidden = await client.get("/api/v1/partner/dashboard")
    assert partner_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_activate_partner_and_repeat_is_idempotent(client: AsyncClient):
    await register_user(client, "new-partner@example.com", first_name="Ann", last_name="Lee")
    first = await become_partner(client)
    assert first.json()["active_role"] == "partner"
    roles = [item["role"] for item in first.json()["user"]["roles"]]
    assert roles == ["partner"]

    dashboard = await client.get("/api/v1/partner/dashboard")
    assert dashboard.status_code == 200

    second = await become_partner(client)
    assert second.status_code == 200
    assert second.json()["active_role"] == "partner"


@pytest.mark.asyncio
async def test_activate_business_then_login_restores_workspace(client: AsyncClient):
    await register_user(client, "new-biz@example.com", first_name="Bob", last_name="Biz")
    activated = await become_business(client, work_email="new-biz@example.com")
    assert activated.json()["active_role"] == "business"
    assert activated.json()["active_business_id"] is not None

    dashboard = await client.get("/api/v1/business/dashboard")
    assert dashboard.status_code == 200

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={
        "email": "new-biz@example.com",
        "password": "testpass123",
    })
    assert login.status_code == 200
    assert login.json()["active_role"] == "business"
    assert login.json()["active_business_id"] is not None


@pytest.mark.asyncio
async def test_second_role_keeps_current_workspace(client: AsyncClient):
    await register_user(client, "second-role@example.com")
    await become_partner(client)
    added = await become_business(client, work_email="second-role@example.com")
    assert added.json()["active_role"] == "partner"
    roles = {item["role"] for item in added.json()["user"]["roles"]}
    assert roles == {"partner", "business"}

    switched = await client.post("/api/v1/me/context", json={"role": "business"})
    assert switched.status_code == 200
    assert switched.json()["active_role"] == "business"

    await client.post("/api/v1/auth/logout")
    login = await client.post("/api/v1/auth/login", json={
        "email": "second-role@example.com",
        "password": "testpass123",
    })
    assert login.json()["active_role"] == "business"


@pytest.mark.asyncio
async def test_business_requires_company_fields(client: AsyncClient):
    await register_user(client, "incomplete-biz@example.com")
    response = await client.post("/api/v1/me/roles/business", json={"name": "Acme"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_search_works_before_role(client: AsyncClient):
    await register_user(client, "onboard-search@example.com")
    from app.modules.finance.lookup.factory import set_lookup_provider_override
    from app.modules.finance.lookup.providers.fake import FakeLegalEntityLookupProvider
    from tests.test_legal_entity_lookup import _candidate

    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate()]
    set_lookup_provider_override(fake)
    response = await client.get(
        "/api/v1/legal-entity-lookup/search",
        params={"query": "ромашка", "context": "business"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["inn"] == "7701234567"


@pytest.mark.asyncio
async def test_business_onboarding_saves_legal_entity(client: AsyncClient, db):
    await register_user(client, "onboard-biz-legal@example.com")
    response = await client.post(
        "/api/v1/me/roles/business",
        json={
            "name": "ООО Ромашка",
            "website": "https://romashka.example.com",
            "country": "RU",
            "work_email": "onboard-biz-legal@example.com",
            "phone": "+79991112233",
            "subject_type": "LEGAL_ENTITY",
            "legal_name": "ООО Ромашка",
            "inn": "7701234567",
            "ogrn": "1234567890123",
            "legal_address": "Москва",
            "contact_name": "Иван Иванов",
            "job_title": "Директор",
        },
    )
    assert response.status_code == 200, response.text
    from sqlalchemy import select
    from app.modules.businesses.models import Business
    from app.modules.finance.models import LegalEntity

    business = (await db.execute(select(Business))).scalars().first()
    entity = await db.get(LegalEntity, business.legal_entity_id)
    assert entity.inn == "7701234567"
    assert entity.legal_name == "ООО Ромашка"
    assert entity.subject_type == "LEGAL_ENTITY"


@pytest.mark.asyncio
async def test_partner_self_employed_onboarding(client: AsyncClient, db):
    await register_user(client, "onboard-npd@example.com", first_name="Мария", last_name="Иванова")
    response = await client.post(
        "/api/v1/me/roles/partner",
        json={
            "subject_type": "INDIVIDUAL",
            "tax_status": "NPD",
            "first_name": "Мария",
            "last_name": "Иванова",
            "inn": "123456789012",
            "country": "RU",
            "city": "Москва",
            "phone": "+79991112233",
        },
    )
    assert response.status_code == 200, response.text
    from sqlalchemy import select
    from app.modules.finance.models import LegalEntity
    from app.modules.partners.models import PartnerProfile

    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    entity = await db.get(LegalEntity, partner.legal_entity_id)
    assert entity.subject_type == "INDIVIDUAL"
    assert entity.tax_status == "NPD"
    assert entity.inn == "123456789012"


@pytest.mark.asyncio
async def test_partner_ip_onboarding(client: AsyncClient, db):
    await register_user(client, "onboard-ip@example.com")
    response = await client.post(
        "/api/v1/me/roles/partner",
        json={
            "subject_type": "SOLE_PROPRIETOR",
            "legal_name": "ИП Иванов Иван",
            "first_name": "Иван",
            "last_name": "Иванов",
            "inn": "123456789012",
            "ogrnip": "123456789012345",
            "legal_address": "Москва",
            "country": "RU",
            "phone": "+79991112233",
        },
    )
    assert response.status_code == 200, response.text
    from sqlalchemy import select
    from app.modules.finance.models import LegalEntity
    from app.modules.partners.models import PartnerProfile

    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    entity = await db.get(LegalEntity, partner.legal_entity_id)
    assert entity.subject_type == "SOLE_PROPRIETOR"
    assert entity.inn == "123456789012"


@pytest.mark.asyncio
async def test_partner_legal_entity_onboarding(client: AsyncClient, db):
    await register_user(client, "onboard-le@example.com")
    response = await client.post(
        "/api/v1/me/roles/partner",
        json={
            "subject_type": "LEGAL_ENTITY",
            "legal_name": "ООО Партнёр",
            "inn": "1234567890",
            "ogrn": "1234567890123",
            "legal_address": "Москва",
            "country": "RU",
            "phone": "+79991112233",
        },
    )
    assert response.status_code == 200, response.text
    legal = await client.get("/api/v1/partner/legal-entity")
    assert legal.json()["legal_entity"]["subject_type"] == "LEGAL_ENTITY"


@pytest.mark.asyncio
async def test_partner_ordinary_individual_rejected_on_create(client: AsyncClient):
    await register_user(client, "onboard-ord@example.com")
    empty = await client.post("/api/v1/me/roles/partner", json={})
    assert empty.status_code == 422
    unknown = await client.post(
        "/api/v1/me/roles/partner",
        json={
            "subject_type": "INDIVIDUAL",
            "tax_status": "UNKNOWN",
            "first_name": "Иван",
            "last_name": "Иванов",
            "inn": "123456789012",
        },
    )
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "PARTNER_INDIVIDUAL_REQUIRES_NPD"
    person = await client.post(
        "/api/v1/me/roles/partner",
        json={"subject_type": "PERSON", "inn": "123456789012"},
    )
    assert person.status_code in {400, 422}


@pytest.mark.asyncio
async def test_partner_invalid_inn_rejected(client: AsyncClient):
    await register_user(client, "onboard-bad-inn@example.com")
    response = await client.post(
        "/api/v1/me/roles/partner",
        json={
            "subject_type": "INDIVIDUAL",
            "tax_status": "NPD",
            "first_name": "Иван",
            "last_name": "Иванов",
            "inn": "123",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FIN_LEGAL_ENTITY_INVALID"


@pytest.mark.asyncio
async def test_business_onboarding_from_lookup_candidate(client: AsyncClient, db):
    from app.modules.finance.lookup.factory import set_lookup_provider_override
    from app.modules.finance.lookup.providers.fake import FakeLegalEntityLookupProvider
    from tests.test_legal_entity_lookup import _candidate, _resolved

    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate()]
    fake.resolve_result = _resolved()
    set_lookup_provider_override(fake)
    await register_user(client, "onboard-lookup@example.com")
    search = await client.get(
        "/api/v1/legal-entity-lookup/search",
        params={"query": "ромашка", "context": "business"},
    )
    candidate_id = search.json()["items"][0]["candidate_id"]
    response = await client.post(
        "/api/v1/me/roles/business",
        json={
            "name": "ООО Ромашка",
            "website": "https://romashka.example.com",
            "country": "RU",
            "work_email": "onboard-lookup@example.com",
            "phone": "+79991112233",
            "candidate_id": candidate_id,
            "subject_type": "LEGAL_ENTITY",
            "legal_name": "ООО Ромашка правленная",
            "inn": "7701234567",
            "ogrn": "1234567890123",
            "legal_address": "Москва, ул. Новая",
        },
    )
    assert response.status_code == 200, response.text
    from sqlalchemy import select
    from app.modules.businesses.models import Business
    from app.modules.finance.models import LegalEntity

    business = (await db.execute(select(Business))).scalars().first()
    entity = await db.get(LegalEntity, business.legal_entity_id)
    assert entity.inn == "7701234567"
    assert entity.legal_name == "ООО Ромашка правленная"
    assert entity.legal_address == "Москва, ул. Новая"
    assert fake.resolve_calls

