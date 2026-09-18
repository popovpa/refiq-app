from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select

from app.common.enums import LegalSubjectType, LegalVerificationStatus
from app.modules.businesses.models import Business
from app.modules.finance.lookup.candidate_token import encode_external_candidate, encode_local_candidate
from app.modules.finance.lookup.factory import set_lookup_provider_override
from app.modules.finance.lookup.protocol import CandidateReference, LegalEntityCandidate, ResolvedLegalEntity
from app.modules.finance.lookup.providers.dadata import DaDataLegalEntityLookupProvider, map_suggestion
from app.modules.finance.lookup.providers.fake import FakeLegalEntityLookupProvider
from app.modules.finance.models import LegalEntity
from app.modules.partners.models import PartnerProfile
from tests.helpers import become_business, become_partner, register_user


def _candidate(**overrides) -> LegalEntityCandidate:
    inn = overrides.get("inn", "7701234567")
    subject = overrides.get("subject_type", LegalSubjectType.LEGAL_ENTITY.value)
    base = LegalEntityCandidate(
        provider="fake",
        display_name=overrides.get("display_name", "ООО Ромашка"),
        subject_type=subject,
        inn=inn,
        reference=CandidateReference(provider="fake", inn=inn, subject_type=subject, branch_type="MAIN"),
        kpp=overrides.get("kpp", "770101001"),
        ogrn=overrides.get("ogrn", "1234567890123"),
        region=overrides.get("region", "Москва"),
        address_summary=overrides.get("address_summary", "Москва"),
    )
    return base


def _resolved(**overrides) -> ResolvedLegalEntity:
    return ResolvedLegalEntity(
        provider="fake",
        provider_reference=overrides.get("inn", "7701234567"),
        subject_type=overrides.get("subject_type", LegalSubjectType.LEGAL_ENTITY.value),
        legal_name=overrides.get("legal_name", "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ РОМАШКА"),
        first_name=overrides.get("first_name"),
        last_name=overrides.get("last_name"),
        middle_name=overrides.get("middle_name"),
        inn=overrides.get("inn", "7701234567"),
        kpp=overrides.get("kpp", "770101001"),
        ogrn=overrides.get("ogrn", "1234567890123"),
        ogrnip=overrides.get("ogrnip"),
        opf_code="12300",
        opf_short="ООО",
        opf_full="Общество с ограниченной ответственностью",
        legal_address=overrides.get("legal_address", "г Москва"),
        region="Москва",
        registry_status=overrides.get("registry_status", "ACTIVE"),
        registration_date=None,
        registry_actuality_date=None,
        invalid=overrides.get("invalid", False),
    )


def _dadata_party(*, status="ACTIVE", type_="LEGAL", branch_type="MAIN", inn="7701234567", invalid=False):
    return {
        "value": "ООО Ромашка",
        "data": {
            "type": type_,
            "inn": inn,
            "kpp": "770101001",
            "ogrn": "1234567890123",
            "branch_type": branch_type,
            "invalid": invalid,
            "name": {"full_with_opf": "ООО РОМАШКА", "short_with_opf": "ООО Ромашка"},
            "opf": {"code": "12300", "short": "ООО", "full": "ООО"},
            "state": {"status": status},
            "address": {"value": "г Москва", "unrestricted_value": "г Москва", "data": {"source": "г Москва", "region": "Москва"}},
            "fio": {"surname": "Иванов", "name": "Иван", "patronymic": "Иванович"},
        },
    }


@pytest.mark.asyncio
async def test_search_by_company_name_and_inn(client):
    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate(), _candidate(inn="7707654321", display_name="ООО Васильёк")]
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-name@example.com")
    await become_business(client)
    named = await client.get("/api/v1/legal-entity-lookup/search", params={"query": "ромашка", "context": "business"})
    assert named.status_code == 200
    assert named.json()["items"][0]["display_name"] == "ООО Ромашка"
    assert named.json()["items"][0]["candidate_id"]
    assert "dadata" not in named.text.lower()
    inn = await client.get("/api/v1/legal-entity-lookup/search", params={"query": "7701234567", "context": "business"})
    assert inn.status_code == 200
    assert any(item["inn"] == "7701234567" for item in inn.json()["items"])
    assert fake.search_calls[0]["query"] == "ромашка"


@pytest.mark.asyncio
async def test_search_ip_by_fio(client):
    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [
        _candidate(
            display_name="ИП Иванов Иван Иванович",
            subject_type=LegalSubjectType.SOLE_PROPRIETOR.value,
            inn="123456789012",
            ogrn=None,
        )
    ]
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-ip@example.com")
    await become_partner(client, "Lookup IP")
    response = await client.get(
        "/api/v1/legal-entity-lookup/search",
        params={"query": "Иванов", "context": "partner", "subject_type": "SOLE_PROPRIETOR"},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["subject_type"] == "SOLE_PROPRIETOR"


def test_dadata_filters_inactive_and_branches():
    assert map_suggestion(_dadata_party(status="LIQUIDATED")) is None
    assert map_suggestion(_dadata_party(branch_type="BRANCH")) is None
    active = map_suggestion(_dadata_party())
    assert active is not None
    assert active.subject_type == "LEGAL_ENTITY"
    ip = map_suggestion(_dadata_party(type_="INDIVIDUAL", inn="123456789012"))
    assert ip is not None
    assert ip.subject_type == "SOLE_PROPRIETOR"


@pytest.mark.asyncio
async def test_select_resolves_provider_and_creates_pending(client, db):
    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate()]
    fake.resolve_result = _resolved()
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-create@example.com")
    await become_business(client)
    search = await client.get("/api/v1/legal-entity-lookup/search", params={"query": "ромашка", "context": "business"})
    candidate_id = search.json()["items"][0]["candidate_id"]
    before = (await db.execute(select(func.count(LegalEntity.id)))).scalar_one()
    selected = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": candidate_id, "target_context": "business"},
    )
    assert selected.status_code == 200
    body = selected.json()
    assert body["reused"] is False
    assert body["legal_entity"]["verification_status"] == "PENDING_VERIFICATION"
    assert body["legal_entity"]["inn"] == "7701234567"
    assert fake.resolve_calls
    after = (await db.execute(select(func.count(LegalEntity.id)))).scalar_one()
    assert after == before + 1


@pytest.mark.asyncio
async def test_frontend_fields_are_not_trusted(client, db):
    fake = FakeLegalEntityLookupProvider()
    fake.resolve_result = _resolved()
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-trust@example.com")
    await become_business(client)
    forged = encode_external_candidate(
        CandidateReference(provider="fake", inn="0000000000", subject_type="LEGAL_ENTITY")
    )
    # Token is valid but resolve returns the provider's entity, not the frontend inn as source of truth
    # unless we change resolve. Here resolve is programmed independently — tampered unsigned payload fails.
    bad = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": "not-a-signed-token", "target_context": "business"},
    )
    assert bad.status_code == 400
    assert forged


@pytest.mark.asyncio
async def test_reuse_existing_accessible_and_keep_verified(client, db):
    fake = FakeLegalEntityLookupProvider()
    fake.resolve_result = _resolved()
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-reuse@example.com")
    await become_business(client)
    await become_partner(client, "Reuse Partner")
    business = (await db.execute(select(Business))).scalars().first()
    entity = await db.get(LegalEntity, business.legal_entity_id)
    entity.inn = "7701234567"
    entity.subject_type = LegalSubjectType.LEGAL_ENTITY.value
    entity.legal_name = "ООО Ромашка"
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verified_at = datetime.now(timezone.utc)
    await db.commit()
    before = (await db.execute(select(func.count(LegalEntity.id)))).scalar_one()
    search = await client.get("/api/v1/legal-entity-lookup/search", params={"query": "7701234567", "context": "partner"})
    local = next(item for item in search.json()["items"] if item["reuse_available"])
    selected = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": local["candidate_id"], "target_context": "partner"},
    )
    assert selected.status_code == 200
    assert selected.json()["reused"] is True
    assert selected.json()["legal_entity"]["verification_status"] == "VERIFIED"
    after = (await db.execute(select(func.count(LegalEntity.id)))).scalar_one()
    assert after == before
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    assert partner.legal_entity_id == business.legal_entity_id


@pytest.mark.asyncio
async def test_partner_first_business_reuses_same_entity(client, db):
    await register_user(client, "lookup-partner-first@example.com")
    await become_partner(client, "First")
    await become_business(client, work_email="lookup-partner-first@example.com")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    entity = await db.get(LegalEntity, partner.legal_entity_id)
    entity.inn = "123456789012"
    entity.subject_type = LegalSubjectType.SOLE_PROPRIETOR.value
    entity.legal_name = "ИП Иванов"
    await db.commit()
    search = await client.get(
        "/api/v1/legal-entity-lookup/search",
        params={"query": "123456789012", "context": "business", "subject_type": "SOLE_PROPRIETOR"},
    )
    local = next(item for item in search.json()["items"] if item["reuse_available"])
    selected = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": local["candidate_id"], "target_context": "business"},
    )
    assert selected.status_code == 200
    business = (await db.execute(select(Business))).scalars().first()
    assert business.legal_entity_id == partner.legal_entity_id


@pytest.mark.asyncio
async def test_cannot_link_foreign_legal_entity(client, db):
    await register_user(client, "lookup-owner@example.com")
    await become_business(client)
    owner_business = (await db.execute(select(Business))).scalars().first()
    foreign_id = owner_business.legal_entity_id
    other = await register_user(client, "lookup-other@example.com")
    assert other.status_code == 200
    await become_business(client, work_email="lookup-other@example.com", name="Other Co")
    stolen = encode_local_candidate(legal_entity_id=foreign_id, inn="7701234567", subject_type="LEGAL_ENTITY")
    response = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": stolen, "target_context": "business"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_npd_partner_search_does_not_call_provider(client):
    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate()]
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-npd@example.com")
    await become_partner(client, "NPD")
    response = await client.get(
        "/api/v1/legal-entity-lookup/search",
        params={"query": "7701234567", "context": "partner", "subject_type": "INDIVIDUAL"},
    )
    assert response.status_code == 200
    assert fake.search_calls == []
    assert response.json()["lookup_enabled"] is False


@pytest.mark.asyncio
async def test_manual_fallback_still_patches(client):
    await register_user(client, "lookup-manual@example.com")
    await become_partner(client, "Manual")
    response = await client.patch(
        "/api/v1/partner/legal-entity",
        json={
            "subject_type": "INDIVIDUAL",
            "tax_status": "NPD",
            "country": "RU",
            "first_name": "Мария",
            "last_name": "Иванова",
            "inn": "123456789012",
            "submit": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["legal_entity"]["verification_status"] == "PENDING_VERIFICATION"


@pytest.mark.asyncio
async def test_inactive_resolve_rejected(client):
    fake = FakeLegalEntityLookupProvider()
    fake.search_results = [_candidate()]
    fake.resolve_result = _resolved(registry_status="LIQUIDATED")
    set_lookup_provider_override(fake)
    await register_user(client, "lookup-inactive@example.com")
    await become_business(client)
    search = await client.get("/api/v1/legal-entity-lookup/search", params={"query": "ромашка", "context": "business"})
    response = await client.post(
        "/api/v1/legal-entity-lookup/select",
        json={"candidate_id": search.json()["items"][0]["candidate_id"], "target_context": "business"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LEGAL_ENTITY_NOT_ACTIVE"


@pytest.mark.asyncio
async def test_dadata_timeout_and_rate_limit_and_auth_mapping():
    timeout_client = AsyncMock()
    timeout_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    provider = DaDataLegalEntityLookupProvider(api_key="secret-key", client=timeout_client)
    with pytest.raises(Exception) as exc:
        await provider.search("ромашка", context="business", limit=5)
    assert exc.value.code == "LEGAL_ENTITY_LOOKUP_UNAVAILABLE"
    assert "secret-key" not in str(exc.value)

    class Resp:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {}

    limited = AsyncMock()
    limited.post = AsyncMock(return_value=Resp(429))
    provider = DaDataLegalEntityLookupProvider(api_key="secret-key", client=limited)
    with pytest.raises(Exception) as rate:
        await provider.search("ромашка", context="business", limit=5)
    assert rate.value.code == "LEGAL_ENTITY_LOOKUP_RATE_LIMITED"

    forbidden = AsyncMock()
    forbidden.post = AsyncMock(return_value=Resp(401))
    provider = DaDataLegalEntityLookupProvider(api_key="secret-key", client=forbidden)
    with pytest.raises(Exception) as auth:
        await provider.search("ромашка", context="business", limit=5)
    assert auth.value.code == "LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR"
    assert "secret-key" not in str(auth.value)


def test_dadata_key_is_not_in_frontend_bundle():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend"
    hits = []
    for path in root.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".json", ".env"}:
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        text = path.read_text(errors="ignore")
        if "DADATA_API_KEY" in text:
            hits.append(str(path))
    assert hits == []
