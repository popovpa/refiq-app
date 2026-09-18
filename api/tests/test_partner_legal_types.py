from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, LegalVerificationStatus, ProfileStatus, TaxStatus
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.models import LegalEntity, PartnerPayoutProfile
from app.modules.partners.models import PartnerProfile
from tests.helpers import become_partner, register_business, register_user


NPD_PAYLOAD = {
    "subject_type": "INDIVIDUAL",
    "tax_status": "NPD",
    "country": "RU",
    "first_name": "Иван",
    "last_name": "Иванов",
    "inn": "123456789012",
    "legal_address": "Москва",
}

IP_USN_PAYLOAD = {
    "subject_type": "SOLE_PROPRIETOR",
    "tax_status": "USN",
    "country": "RU",
    "legal_name": "ИП Иванов",
    "first_name": "Иван",
    "last_name": "Иванов",
    "inn": "123456789012",
    "ogrnip": "123456789012345",
    "legal_address": "Москва",
}

IP_NPD_PAYLOAD = {**IP_USN_PAYLOAD, "tax_status": "NPD"}

LEGAL_USN_PAYLOAD = {
    "subject_type": "LEGAL_ENTITY",
    "tax_status": "USN",
    "country": "RU",
    "legal_name": "ООО Партнёр",
    "inn": "1234567890",
    "ogrn": "1234567890123",
    "legal_address": "Москва",
}


async def _partner_entity(db: AsyncSession) -> tuple[PartnerProfile, LegalEntity]:
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    entity = await db.get(LegalEntity, partner.legal_entity_id)
    assert entity is not None
    return partner, entity


@pytest.mark.asyncio
async def test_partner_individual_npd_is_valid(client: AsyncClient):
    await register_user(client, "p-npd@example.com")
    await become_partner(client, "NPD Partner")
    response = await client.patch("/api/v1/partner/legal-entity", json={**NPD_PAYLOAD, "submit": True})
    assert response.status_code == 200, response.text
    body = response.json()["legal_entity"]
    assert body["subject_type"] == "INDIVIDUAL"
    assert body["tax_status"] == "NPD"
    assert body["verification_status"] == "PENDING_VERIFICATION"


@pytest.mark.asyncio
async def test_partner_individual_unknown_is_rejected(client: AsyncClient, db: AsyncSession):
    await register_user(client, "p-unknown@example.com")
    await become_partner(client, "Unknown Individual")
    response = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**NPD_PAYLOAD, "tax_status": "UNKNOWN", "submit": True},
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "PARTNER_INDIVIDUAL_REQUIRES_NPD"
    _, entity = await _partner_entity(db)
    assert entity.tax_status == TaxStatus.UNKNOWN.value


@pytest.mark.asyncio
async def test_partner_individual_usn_is_rejected(client: AsyncClient):
    await register_user(client, "p-usn@example.com")
    await become_partner(client, "USN Individual")
    response = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**NPD_PAYLOAD, "tax_status": "USN", "submit": False},
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "PARTNER_INDIVIDUAL_REQUIRES_NPD"


@pytest.mark.asyncio
async def test_partner_sole_proprietor_usn_is_valid(client: AsyncClient):
    await register_user(client, "p-ip-usn@example.com")
    await become_partner(client, "IP USN")
    response = await client.patch("/api/v1/partner/legal-entity", json={**IP_USN_PAYLOAD, "submit": True})
    assert response.status_code == 200, response.text
    assert response.json()["legal_entity"]["tax_status"] == "USN"


@pytest.mark.asyncio
async def test_partner_sole_proprietor_npd_is_valid(client: AsyncClient):
    await register_user(client, "p-ip-npd@example.com")
    await become_partner(client, "IP NPD")
    response = await client.patch("/api/v1/partner/legal-entity", json={**IP_NPD_PAYLOAD, "submit": True})
    assert response.status_code == 200, response.text
    assert response.json()["legal_entity"]["subject_type"] == "SOLE_PROPRIETOR"
    assert response.json()["legal_entity"]["tax_status"] == "NPD"


@pytest.mark.asyncio
async def test_partner_legal_entity_usn_is_valid(client: AsyncClient):
    await register_user(client, "p-le-usn@example.com")
    await become_partner(client, "LE USN")
    response = await client.patch("/api/v1/partner/legal-entity", json={**LEGAL_USN_PAYLOAD, "submit": True})
    assert response.status_code == 200, response.text
    assert response.json()["legal_entity"]["subject_type"] == "LEGAL_ENTITY"
    assert response.json()["legal_entity"]["tax_status"] == "USN"


@pytest.mark.asyncio
async def test_ordinary_individual_is_not_payout_eligible(client: AsyncClient, db: AsyncSession):
    await register_user(client, "p-ord@example.com")
    await become_partner(client, "Ordinary")
    partner, entity = await _partner_entity(db)
    entity.subject_type = LegalSubjectType.INDIVIDUAL.value
    entity.tax_status = TaxStatus.UNKNOWN.value
    entity.first_name = "Иван"
    entity.last_name = "Иванов"
    entity.inn = "123456789012"
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verified_at = datetime.now(timezone.utc)
    profile = (
        await db.execute(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner.id))
    ).scalar_one()
    profile.payout_method = "bank_transfer"
    profile.bank_account = "40817810099910004312"
    profile.bank_bik = "044525225"
    profile.status = ProfileStatus.VERIFIED.value
    profile.verified_at = datetime.now(timezone.utc)
    await db.commit()

    result = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert result.eligible is False
    assert result.reason_code == "UNSUPPORTED_PARTNER_TYPE"


@pytest.mark.asyncio
async def test_npd_individual_continues_past_type_check(client: AsyncClient, db: AsyncSession):
    await register_user(client, "p-npd-next@example.com")
    await become_partner(client, "NPD Next")
    partner, entity = await _partner_entity(db)
    entity.subject_type = LegalSubjectType.INDIVIDUAL.value
    entity.tax_status = TaxStatus.NPD.value
    entity.first_name = "Иван"
    entity.last_name = "Иванов"
    entity.inn = "123456789012"
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verified_at = datetime.now(timezone.utc)
    await db.commit()

    result = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert result.eligible is False
    assert result.reason_code != "UNSUPPORTED_PARTNER_TYPE"
    assert result.reason_code in {"PAYOUT_PROFILE_MISSING", "PAYOUT_PROFILE_NOT_VERIFIED", "PAYMENT_DETAILS_INVALID"}


@pytest.mark.asyncio
async def test_business_legal_rules_unchanged(client: AsyncClient):
    await register_business(client, "biz-legal@example.com")
    response = await client.patch(
        "/api/v1/business/legal-entity",
        json={
            "subject_type": "LEGAL_ENTITY",
            "tax_status": "USN",
            "legal_name": "ООО Бизнес",
            "inn": "1234567890",
            "ogrn": "1234567890123",
            "legal_address": "Москва",
            "submit": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["legal_entity"]["subject_type"] == "LEGAL_ENTITY"

    individual = await client.patch(
        "/api/v1/business/legal-entity",
        json={"subject_type": "INDIVIDUAL", "tax_status": "UNKNOWN", "submit": False},
    )
    assert individual.status_code == 200, individual.text
    assert "error" not in individual.json()
    assert individual.json()["legal_entity"]["subject_type"] == "INDIVIDUAL"
    assert individual.json()["legal_entity"]["tax_status"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_legacy_individual_is_not_auto_converted_to_npd(client: AsyncClient, db: AsyncSession):
    await register_user(client, "p-legacy@example.com")
    await become_partner(client, "Legacy Individual")
    current = await client.get("/api/v1/partner/legal-entity")
    assert current.status_code == 200
    entity = current.json()["legal_entity"]
    assert entity["subject_type"] == "INDIVIDUAL"
    assert entity["tax_status"] == "UNKNOWN"

    rejected = await client.patch(
        "/api/v1/partner/legal-entity",
        json={"legal_name": "Не менять налог", "submit": False},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "PARTNER_INDIVIDUAL_REQUIRES_NPD"

    db.expire_all()
    _, stored = await _partner_entity(db)
    assert stored.subject_type == LegalSubjectType.INDIVIDUAL.value
    assert stored.tax_status == TaxStatus.UNKNOWN.value
    assert stored.tax_status != TaxStatus.NPD.value


@pytest.mark.asyncio
async def test_partner_legal_entity_rejects_npd_and_patent(client: AsyncClient):
    await register_user(client, "p-le-bad-tax@example.com")
    await become_partner(client, "LE Bad Tax")
    npd = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**LEGAL_USN_PAYLOAD, "tax_status": "NPD", "submit": False},
    )
    assert npd.status_code == 400
    assert npd.json()["error"]["code"] == "PARTNER_TAX_STATUS_INVALID"
    patent = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**LEGAL_USN_PAYLOAD, "tax_status": "PATENT", "submit": True},
    )
    assert patent.status_code == 400
    assert patent.json()["error"]["code"] == "PARTNER_TAX_STATUS_INVALID"


@pytest.mark.asyncio
async def test_partner_ip_draft_may_omit_tax_status(client: AsyncClient):
    await register_user(client, "p-ip-draft@example.com")
    await become_partner(client, "IP Draft")
    draft = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**IP_USN_PAYLOAD, "tax_status": "UNKNOWN", "submit": False},
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["legal_entity"]["tax_status"] == "UNKNOWN"
    submit = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**IP_USN_PAYLOAD, "tax_status": "UNKNOWN", "submit": True},
    )
    assert submit.status_code == 400
    assert submit.json()["error"]["code"] == "PARTNER_TAX_STATUS_INVALID"
