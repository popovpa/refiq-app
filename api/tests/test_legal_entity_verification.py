from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalVerificationStatus, ProfileStatus
from app.modules.businesses.models import Business
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.models import FinancialAuditEvent, LegalEntity, LegalEntityVerificationAttempt, PartnerPayoutProfile
from app.modules.partners.models import PartnerProfile
from tests.helpers import become_partner, register_business, register_user
from tests.test_admin import ADMIN_PASSWORD, _login


COMPLETE_SP = {
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


async def _submit_partner_legal(client: AsyncClient, extra: dict | None = None):
    payload = {**COMPLETE_SP, "submit": True, **(extra or {})}
    response = await client.patch("/api/v1/partner/legal-entity", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["legal_entity"]


@pytest.mark.asyncio
async def test_admin_verify_pending_legal_entity(client: AsyncClient, admin_client: AsyncClient, db: AsyncSession):
    await register_user(client, "verify-p@example.com")
    await become_partner(client, "Verify Partner")
    entity = await _submit_partner_legal(client)
    assert entity["verification_status"] == LegalVerificationStatus.PENDING_VERIFICATION.value

    await _login(admin_client, email="verify-admin@refiq.ru", role="finance")
    listed = await admin_client.get("/api/admin/v1/legal-entities", params={"status": "PENDING_VERIFICATION"})
    assert listed.status_code == 200
    assert any(item["id"] == entity["id"] for item in listed.json()["items"])
    assert listed.json()["items"][0]["verification_status"] == LegalVerificationStatus.PENDING_VERIFICATION.value

    verified = await admin_client.post(
        f"/api/admin/v1/legal-entities/{entity['id']}/verify",
        json={"comment": "Проверено вручную"},
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["verification_status"] == LegalVerificationStatus.VERIFIED.value
    assert body["verification_source"] == "MANUAL"
    assert body["verified_at"]
    assert body["attempts"]
    assert body["attempts"][0]["provider"] == "MANUAL"
    assert body["attempts"][0]["status"] == "SUCCESS"

    db.expire_all()
    stored = await db.get(LegalEntity, entity["id"])
    assert stored.verification_status == LegalVerificationStatus.VERIFIED.value
    assert stored.verification_source == "MANUAL"
    assert stored.verified_at is not None
    audit = (
        await db.execute(
            select(FinancialAuditEvent).where(
                FinancialAuditEvent.action == "LEGAL_ENTITY_VERIFIED",
                FinancialAuditEvent.entity_id == str(entity["id"]),
            )
        )
    ).scalars().all()
    assert audit
    attempts = (
        await db.execute(
            select(LegalEntityVerificationAttempt).where(
                LegalEntityVerificationAttempt.legal_entity_id == entity["id"]
            )
        )
    ).scalars().all()
    assert len(attempts) == 1

    again = await admin_client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})
    assert again.status_code == 200
    db.expire_all()
    attempts_after = (
        await db.execute(
            select(LegalEntityVerificationAttempt).where(
                LegalEntityVerificationAttempt.legal_entity_id == entity["id"]
            )
        )
    ).scalars().all()
    assert len(attempts_after) == 1


@pytest.mark.asyncio
async def test_admin_reject_pending_legal_entity(client: AsyncClient, admin_client: AsyncClient, db: AsyncSession):
    await register_user(client, "reject-p@example.com")
    await become_partner(client, "Reject Partner")
    entity = await _submit_partner_legal(client)
    await _login(admin_client, email="reject-admin@refiq.ru", role="finance")
    rejected = await admin_client.post(
        f"/api/admin/v1/legal-entities/{entity['id']}/reject",
        json={"reason_code": "INN_NOT_FOUND", "comment": "ИНН не найден в официальном источнике"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["verification_status"] == LegalVerificationStatus.REJECTED.value
    assert body["verification_reason_code"] == "INN_NOT_FOUND"
    assert body["verification_reason"] == "ИНН не найден"
    assert body["attempts"][0]["status"] == "FAILED"
    assert body["attempts"][0]["comment"] == "ИНН не найден в официальном источнике"

    public = await client.get("/api/v1/partner/legal-entity")
    assert public.status_code == 200
    public_entity = public.json()["legal_entity"]
    assert public_entity["verification_status"] == "REJECTED"
    assert public_entity["verification_reason"] == "ИНН не найден"
    assert "verification_comment" not in public_entity
    assert public_entity.get("attempts") is None

    audit = (
        await db.execute(
            select(FinancialAuditEvent).where(FinancialAuditEvent.action == "LEGAL_ENTITY_REJECTED")
        )
    ).scalars().all()
    assert audit


@pytest.mark.asyncio
async def test_non_admin_cannot_verify(client: AsyncClient, admin_client: AsyncClient):
    await register_user(client, "plain@example.com")
    await become_partner(client, "Plain")
    entity = await _submit_partner_legal(client)

    missing = await admin_client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})
    assert missing.status_code == 401

    public_admin = await client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})
    assert public_admin.status_code == 404

    gone = await client.post(f"/api/v1/finance/test/legal-entities/{entity['id']}/verify", json={})
    assert gone.status_code in {404, 405}

    await _login(admin_client, email="support-le@refiq.ru", role="support")
    forbidden = await admin_client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_public_schema_rejects_verification_status(client: AsyncClient):
    await register_user(client, "inject-p@example.com")
    await become_partner(client, "Inject")
    injected = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**COMPLETE_SP, "submit": True, "verification_status": "VERIFIED"},
    )
    assert injected.status_code == 422

    await register_business(client, "inject-b@example.com")
    business_injected = await client.patch(
        "/api/v1/business/legal-entity",
        json={**COMPLETE_SP, "subject_type": "LEGAL_ENTITY", "inn": "1234567890", "ogrn": "1234567890123", "submit": True, "verification_status": "VERIFIED"},
    )
    assert business_injected.status_code == 422


@pytest.mark.asyncio
async def test_conflicting_admin_actions_return_conflict(client: AsyncClient, admin_client: AsyncClient):
    await register_user(client, "race-p@example.com")
    await become_partner(client, "Race")
    entity = await _submit_partner_legal(client)
    await _login(admin_client, email="race-admin@refiq.ru")
    first = await admin_client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})
    assert first.status_code == 200
    second = await admin_client.post(
        f"/api/admin/v1/legal-entities/{entity['id']}/reject",
        json={"reason_code": "DATA_MISMATCH"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "LEGAL_ENTITY_STATUS_CHANGED"
    detail = await admin_client.get(f"/api/admin/v1/legal-entities/{entity['id']}")
    assert detail.json()["verification_status"] == "VERIFIED"
    assert len(detail.json()["attempts"]) == 1


@pytest.mark.asyncio
async def test_editing_verified_inn_requires_reverification(
    client: AsyncClient, admin_client: AsyncClient, db: AsyncSession
):
    await register_user(client, "reverify@example.com")
    await become_partner(client, "Reverify")
    entity = await _submit_partner_legal(client)
    await _login(admin_client, email="reverify-admin@refiq.ru", role="finance")
    await admin_client.post(f"/api/admin/v1/legal-entities/{entity['id']}/verify", json={})

    updated = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**COMPLETE_SP, "inn": "123456789099", "submit": False},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["legal_entity"]
    assert body["verification_status"] == LegalVerificationStatus.PENDING_VERIFICATION.value
    assert body["verified_at"] is None

    db.expire_all()
    stored = await db.get(LegalEntity, entity["id"])
    assert stored.verification_source is None
    events = (
        await db.execute(
            select(FinancialAuditEvent).where(
                FinancialAuditEvent.action == "LEGAL_ENTITY_REVERIFICATION_REQUIRED",
                FinancialAuditEvent.entity_id == str(entity["id"]),
            )
        )
    ).scalars().all()
    assert events


@pytest.mark.asyncio
async def test_rejected_resubmit_goes_pending(client: AsyncClient, admin_client: AsyncClient):
    await register_user(client, "resubmit@example.com")
    await become_partner(client, "Resubmit")
    entity = await _submit_partner_legal(client)
    await _login(admin_client, email="resubmit-admin@refiq.ru", role="finance")
    await admin_client.post(
        f"/api/admin/v1/legal-entities/{entity['id']}/reject",
        json={"reason_code": "DATA_MISMATCH"},
    )
    draft = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**COMPLETE_SP, "legal_name": "ИП Иванов испр.", "submit": False},
    )
    assert draft.json()["legal_entity"]["verification_status"] == "REJECTED"
    resubmitted = await client.patch(
        "/api/v1/partner/legal-entity",
        json={**COMPLETE_SP, "legal_name": "ИП Иванов испр.", "submit": True},
    )
    assert resubmitted.json()["legal_entity"]["verification_status"] == "PENDING_VERIFICATION"


@pytest.mark.asyncio
async def test_payout_requires_verified_legal_entity(client: AsyncClient, db: AsyncSession):
    await register_user(client, "gate@example.com")
    await become_partner(client, "Gate")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _submit_partner_legal(client)
    service = PartnerPayoutEligibilityService(db)

    pending = await service.check_payout_eligibility(partner.id)
    assert pending.eligible is False
    assert pending.reason_code == "LEGAL_ENTITY_NOT_VERIFIED"

    entity = await db.get(LegalEntity, partner.legal_entity_id)
    entity.verification_status = LegalVerificationStatus.REJECTED.value
    await db.commit()
    rejected = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert rejected.eligible is False
    assert rejected.reason_code == "LEGAL_ENTITY_NOT_VERIFIED"

    entity = await db.get(LegalEntity, partner.legal_entity_id)
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verified_at = datetime.now(timezone.utc)
    profile = (
        await db.execute(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner.id))
    ).scalar_one()
    profile.payout_method = "bank_transfer"
    profile.bank_account = "40817810099910004312"
    profile.bank_bik = "044525225"
    profile.bank_name = "Т-Банк"
    profile.status = ProfileStatus.VERIFIED.value
    await db.commit()
    ok = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert ok.eligible is True


@pytest.mark.asyncio
async def test_reject_other_requires_comment(client: AsyncClient, admin_client: AsyncClient):
    await register_user(client, "other@example.com")
    await become_partner(client, "Other")
    entity = await _submit_partner_legal(client)
    await _login(admin_client, email="other-admin@refiq.ru", role="finance")
    missing = await admin_client.post(
        f"/api/admin/v1/legal-entities/{entity['id']}/reject",
        json={"reason_code": "OTHER"},
    )
    assert missing.status_code == 422
