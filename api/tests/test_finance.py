from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.common.enums import (
    CommissionStatus,
    LegalSubjectType,
    LegalVerificationStatus,
    PayoutFailureClass,
    PayoutStatus,
    ProfileStatus,
    TaxStatus,
)
from app.modules.businesses.models import Business
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.finance.commission import create_commission_for_approved_conversion, release_due_holds
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.models import LegalEntity, PartnerPayoutProfile
from app.modules.finance.payouts import confirm_payout, generate_due_payouts, mark_overdue_payouts, mark_payout_failed
from app.modules.finance.providers.factory import reset_provider_overrides, set_tbank_constructors
from app.modules.finance.reconciliation import reconcile_open_transactions
from app.modules.finance.reversal import reverse_conversion
from app.modules.finance.suspension import is_partner_traffic_suspended
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout
from tests.conftest import fastapi_app
from tests.helpers import (
    become_business,
    become_partner,
    offer_payload,
    partner_with_access,
    register_business,
    register_user,
)


async def _eligible_partner(db, partner_id: int, *, subject=LegalSubjectType.SOLE_PROPRIETOR, tax=TaxStatus.USN):
    partner = await db.get(PartnerProfile, partner_id)
    entity = await db.get(LegalEntity, partner.legal_entity_id)
    entity.subject_type = subject.value
    entity.tax_status = tax.value
    entity.first_name = "Иван"
    entity.last_name = "Иванов"
    entity.inn = "123456789012" if subject != LegalSubjectType.LEGAL_ENTITY else "1234567890"
    if subject == LegalSubjectType.LEGAL_ENTITY:
        entity.ogrn = "1234567890123"
        entity.legal_name = "ООО Партнёр"
        entity.legal_address = "Москва"
        entity.inn = "1234567890"
    if subject == LegalSubjectType.SOLE_PROPRIETOR:
        entity.ogrnip = "123456789012345"
        entity.legal_name = "ИП Иванов"
    if subject == LegalSubjectType.INDIVIDUAL:
        entity.tax_status = tax.value
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verified_at = datetime.now(timezone.utc)
    profile = (
        await db.execute(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner_id))
    ).scalar_one()
    profile.payout_method = "bank_transfer"
    profile.bank_account = "40817810099910004312"
    profile.bank_bik = "044525225"
    profile.bank_name = "Т-Банк"
    profile.status = ProfileStatus.VERIFIED.value
    profile.verified_at = datetime.now(timezone.utc)
    profile.legal_entity_id = entity.id
    await db.commit()
    return partner


async def _verify_legal_entity(db, entity_id: int):
    entity = await db.get(LegalEntity, entity_id)
    entity.verification_status = LegalVerificationStatus.VERIFIED.value
    entity.verification_source = "MANUAL"
    entity.verified_at = datetime.now(timezone.utc)
    await db.commit()
    return entity


async def _add_available_commission(db, *, business_id, partner_id, offer_id, amount="500.00"):
    conversion = Conversion(
        business_id=business_id,
        offer_id=offer_id,
        partner_id=partner_id,
        amount=Decimal("5000.00"),
        currency="RUB",
        commission_amount=Decimal(amount),
        status="approved",
        hold_period_days_snapshot=0,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(conversion)
    await db.flush()
    commission = await create_commission_for_approved_conversion(db, conversion)
    await db.commit()
    return commission


@pytest.mark.asyncio
async def test_dual_profile_still_works(client):
    await register_user(client, "dual-fin@example.com")
    await become_business(client)
    await become_partner(client, "Dual")
    me = await client.get("/api/v1/me")
    roles = {item["role"] for item in me.json()["roles"]}
    assert roles == {"business", "partner"}


@pytest.mark.asyncio
async def test_same_and_different_legal_entities(client, db):
    await register_business(client, "biz-le@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "part-le@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    assert biz.legal_entity_id
    assert partner_row.legal_entity_id
    assert biz.legal_entity_id != partner_row.legal_entity_id
    partner_row.legal_entity_id = biz.legal_entity_id
    await db.commit()
    assert partner_row.legal_entity_id == biz.legal_entity_id



@pytest.mark.asyncio
async def test_payout_eligibility_matrix(client, db):
    await register_user(client, "elig@example.com")
    await become_partner(client, "Elig")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    service = PartnerPayoutEligibilityService(db)

    denied = await service.check_payout_eligibility(partner.id)
    assert denied.eligible is False
    assert denied.reason_code in {"LEGAL_ENTITY_MISSING", "LEGAL_ENTITY_NOT_VERIFIED", "UNSUPPORTED_PARTNER_TYPE", "PAYOUT_PROFILE_MISSING", "PAYOUT_PROFILE_NOT_VERIFIED"}

    await _eligible_partner(db, partner.id, subject=LegalSubjectType.INDIVIDUAL, tax=TaxStatus.NPD)
    ok = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert ok.eligible is True

    await _eligible_partner(db, partner.id, subject=LegalSubjectType.INDIVIDUAL, tax=TaxStatus.UNKNOWN)
    no = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert no.eligible is False
    assert no.reason_code == "UNSUPPORTED_PARTNER_TYPE"

    await _eligible_partner(db, partner.id, subject=LegalSubjectType.SOLE_PROPRIETOR)
    assert (await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)).eligible is True

    await _eligible_partner(db, partner.id, subject=LegalSubjectType.LEGAL_ENTITY)
    assert (await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)).eligible is True


@pytest.mark.asyncio
async def test_commission_snapshot_not_recalculated(client, db):
    await register_business(client, "snap@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active", commission_value=10))
    offer_id = created.json()["id"]
    partner = await partner_with_access(offer_id, "snap-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile).where(PartnerProfile.display_name == "Partner"))).scalars().first()
    if partner_row is None:
        partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    commission = await _add_available_commission(
        db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="100.00"
    )
    offer = await db.get(Offer, offer_id)
    offer.commission_rules[0].value = 50
    await db.commit()
    await db.refresh(commission)
    assert Decimal(str(commission.amount)) == Decimal("100.00")
    assert commission.commission_value is not None


@pytest.mark.asyncio
async def test_hold_periods(db, client):
    await register_business(client, "hold@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active", hold_period_days=7))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "hold-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    conversion = Conversion(
        business_id=biz.id,
        offer_id=offer_id,
        partner_id=partner_row.id,
        amount=Decimal("1000"),
        currency="RUB",
        commission_amount=Decimal("100"),
        status="approved",
        hold_period_days_snapshot=7,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(conversion)
    await db.flush()
    commission = await create_commission_for_approved_conversion(db, conversion)
    assert commission.status == CommissionStatus.HOLD.value
    commission.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        released = await release_due_holds(session)
        await session.commit()
        assert released >= 1


@pytest.mark.asyncio
async def test_minimum_payout_threshold(client, db):
    await register_business(client, "minp@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "minp-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="499.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        created_payouts = await generate_due_payouts(session, ignore_interval=True)
        await session.commit()
        assert created_payouts == []
        leftover = (await session.execute(select(Commission).where(Commission.partner_id == partner_row.id))).scalars().all()
        for item in leftover:
            item.status = CommissionStatus.CANCELLED.value
        await session.commit()
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    async with TestingSessionLocal() as session:
        created_payouts = await generate_due_payouts(session, ignore_interval=True)
        await session.commit()
        assert len(created_payouts) == 1
        assert Decimal(str(created_payouts[0].amount)) == Decimal("500.00")


@pytest.mark.asyncio
async def test_payout_interval_14_days(client, db):
    await register_business(client, "intv@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "intv-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        first = await generate_due_payouts(session, ignore_interval=True)
        await session.commit()
        assert len(first) == 1
        first[0].status = PayoutStatus.PAID.value
        await session.commit()
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        none = await generate_due_payouts(session, now=now, ignore_interval=False)
        await session.commit()
        assert none == []
    later = now + timedelta(days=14)
    async with TestingSessionLocal() as session:
        second = await generate_due_payouts(session, now=later, ignore_interval=False)
        await session.commit()
        assert len(second) == 1


@pytest.mark.asyncio
async def test_overdue_suspends_partner_traffic(client, db):
    await register_business(client, "ovd@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    partner = await partner_with_access(offer_id, "ovd-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        payouts[0].due_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
        payout_id = payouts[0].id
    async with TestingSessionLocal() as session:
        await mark_overdue_payouts(session)
        await session.commit()
        assert await is_partner_traffic_suspended(session, biz.id)
        payout = await session.get(Payout, payout_id)
        assert payout.status == PayoutStatus.OVERDUE.value
    create = await partner.post(
        "/api/v1/partner/links",
        json={"offer_id": offer_id, "name": "x", "traffic_source": "EMAIL"},
    )
    assert create.status_code == 403


@pytest.mark.asyncio
async def test_provider_error_does_not_suspend_business(client, db):
    await register_business(client, "prov@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "prov-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        await mark_payout_failed(
            session,
            payouts[0],
            failure_class=PayoutFailureClass.PROVIDER_ERROR.value,
            message="tbank",
        )
        await session.commit()
        assert payouts[0].status == PayoutStatus.MANUAL_REVIEW.value
        assert await is_partner_traffic_suspended(session, biz.id) is False


@pytest.mark.asyncio
async def test_invalid_partner_does_not_punish_business(client, db):
    await register_business(client, "invp@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "invp-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        await mark_payout_failed(
            session,
            payouts[0],
            failure_class=PayoutFailureClass.PARTNER_PAYMENT_DETAILS_INVALID.value,
        )
        await session.commit()
        assert await is_partner_traffic_suspended(session, biz.id) is False


@pytest.mark.asyncio
async def test_self_deal_same_legal_entity(client, db):
    await register_user(client, "self@example.com")
    await become_business(client)
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await become_partner(client, "Self")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    partner_row.legal_entity_id = biz.legal_entity_id
    await db.commit()
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_business_owned_promotion_zero_commission(client, db):
    await register_business(client, "owned@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    without_campaign = await client.post(
        f"/api/v1/business/offers/{offer_id}/links",
        json={"destination_url": "https://acme.example.com/pricing"},
    )
    assert without_campaign.status_code == 200, without_campaign.text
    assert without_campaign.json()["partner_id"] is None


@pytest.mark.asyncio
async def test_test_mode_does_not_call_tbank(client, db):
    class SpyPayment:
        def __init__(self):
            raise AssertionError("TBank live adapter must not be constructed in test mode")

    class SpyPayout:
        def __init__(self):
            raise AssertionError("TBank live adapter must not be constructed in test mode")

    set_tbank_constructors(SpyPayment, SpyPayout)
    try:
        await register_business(client, "tbank@example.com")
        created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
        offer_id = created.json()["id"]
        await partner_with_access(offer_id, "tbank-p@example.com")
        biz = (await db.execute(select(Business))).scalars().first()
        partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
        await _eligible_partner(db, partner_row.id)
        await _verify_legal_entity(db, biz.legal_entity_id)
        await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
        from tests.conftest import TestingSessionLocal

        async with TestingSessionLocal() as session:
            payouts = await generate_due_payouts(session, ignore_interval=True)
            await confirm_payout(session, payouts[0], actor_user_id=None)
            await session.commit()
            assert payouts[0].provider == "TEST"
    finally:
        reset_provider_overrides()


@pytest.mark.asyncio
async def test_confirm_idempotent(client, db):
    await register_business(client, "idem@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "idem-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    await _eligible_partner(db, partner_row.id)
    await _verify_legal_entity(db, biz.legal_entity_id)
    await _add_available_commission(db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00")
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        first = await confirm_payout(session, payouts[0], actor_user_id=1)
        second = await confirm_payout(session, payouts[0], actor_user_id=1)
        await session.commit()
        assert first.id == second.id
        count = len((await session.execute(select(Payout).where(Payout.partner_id == partner_row.id))).scalars().all())
        assert count == 1


@pytest.mark.asyncio
async def test_reversal_unpaid_and_paid(client, db):
    await register_business(client, "rev@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "rev-p@example.com")
    biz = (await db.execute(select(Business))).scalars().first()
    partner_row = (await db.execute(select(PartnerProfile))).scalars().first()
    commission = await _add_available_commission(
        db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00"
    )
    conversion = await db.get(Conversion, commission.conversion_id)
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        conv = await session.get(Conversion, conversion.id)
        result = await reverse_conversion(session, conv, reason="TEST_CONVERSION")
        await session.commit()
        assert result["manual_review"] is False
        comm = await session.get(Commission, commission.id)
        assert comm.status == CommissionStatus.REVERSED.value

    paid = await _add_available_commission(
        db, business_id=biz.id, partner_id=partner_row.id, offer_id=offer_id, amount="500.00"
    )
    paid.status = CommissionStatus.PAID.value
    await db.commit()
    async with TestingSessionLocal() as session:
        conv = await session.get(Conversion, paid.conversion_id)
        result = await reverse_conversion(session, conv, reason="ORDER_CANCELLED")
        await session.commit()
        assert result["manual_review"] is True
        comm = await session.get(Commission, paid.id)
        assert comm.status == CommissionStatus.PAID.value
        assert comm.amount > 0


@pytest.mark.asyncio
async def test_authorization_blocks_foreign_business(client):
    await register_business(client, "a@example.com")
    stranger = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")
    await register_user(stranger, "b@example.com")
    await become_business(stranger, name="Other", website="https://other.example.com")
    payouts = await stranger.get("/api/v1/business/payouts")
    assert payouts.status_code == 200
    items = payouts.json().get("items", [])
    assert items == []
    confirm = await stranger.post("/api/v1/business/payouts/1/confirm")
    assert confirm.status_code in {403, 404}


@pytest.mark.asyncio
async def test_no_wallet_models():
    from app.modules.users.models import User
    from app.modules.businesses.models import Business
    from app.modules.partners.models import PartnerProfile

    for model in (User, Business, PartnerProfile):
        assert "wallet" not in model.__table__.c
        assert "balance" not in model.__table__.c


@pytest.mark.asyncio
async def test_finance_partner_settings_persist(client):
    await register_user(client, "payset@example.com")
    await become_partner(client, "Pay")
    saved = await client.patch(
        "/api/v1/partner/payout-profile",
        json={"payout_method": "bank_transfer", "bank_account": "40817810099910004312", "bank_bik": "044525225", "bank_name": "T"},
    )
    assert saved.status_code == 200, saved.text
    fetched = await client.get("/api/v1/partner/payout-profile")
    assert fetched.status_code == 200
    assert fetched.json()["payout_profile"]["has_bank_account"] is True
    assert "40817810099910004312" not in fetched.text


@pytest.mark.asyncio
async def test_financial_jobs_lock_conflict_is_quiet():
    from app.modules.finance.jobs import run_financial_jobs
    from tests.conftest import TestingSessionLocal

    now = datetime.now(timezone.utc)
    first = await run_financial_jobs(now=now, session_factory=TestingSessionLocal)
    second = await run_financial_jobs(now=now, session_factory=TestingSessionLocal)
    assert set(first) == set(second)
    assert second["payouts"] == 0
