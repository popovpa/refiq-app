from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CommissionStatus, LegalSubjectType, PayoutStatus, ProfileStatus, TaxStatus
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.finance.commission import create_commission_for_approved_conversion
from app.modules.finance.eligibility import PartnerPayoutEligibilityService
from app.modules.finance.models import FinancialAuditEvent, PartnerPayoutProfile
from app.modules.finance.payouts import generate_due_payouts
from app.modules.finance.repair_self_promotion import repair_self_promotion
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout, PayoutItem
from app.modules.users.models import User
from tests.helpers import (
    become_business,
    become_partner,
    offer_payload,
    partner_with_access,
    register_business,
    register_user,
)
from tests.test_finance import _eligible_partner, _verify_legal_entity


async def _dual_user_offer(client: AsyncClient, email: str, name: str = "Self Offer"):
    await register_user(client, email)
    await become_business(client)
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active", name=name))
    assert created.status_code == 200, created.text
    await become_partner(client, "Dual Partner")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    return created.json()["id"]


async def _plant_access(db: AsyncSession, offer_id: int, partner_id: int) -> OfferPartnerAccess:
    access = OfferPartnerAccess(
        offer_id=offer_id,
        partner_id=partner_id,
        status="approved",
        source="test",
        approved_at=datetime.now(timezone.utc),
    )
    db.add(access)
    await db.commit()
    return access


async def _raw_available_commission(db: AsyncSession, *, business_id, partner_id, offer_id, amount="500.00"):
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
    commission = Commission(
        conversion_id=conversion.id,
        offer_id=offer_id,
        business_id=business_id,
        partner_id=partner_id,
        amount=Decimal(amount),
        currency="RUB",
        status=CommissionStatus.AVAILABLE.value,
        hold_period_days=0,
        available_at=datetime.now(timezone.utc),
    )
    db.add(commission)
    await db.commit()
    return commission


@pytest.mark.asyncio
async def test_same_user_cannot_join_own_offer(client: AsyncClient):
    offer_id = await _dual_user_offer(client, "self-join@example.com")
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403
    assert join.json()["error"]["code"] in {"OWN_BUSINESS_OFFER", "SAME_USER_BUSINESS_MEMBER", "FIN_SELF_DEAL_FORBIDDEN"}


@pytest.mark.asyncio
async def test_same_user_different_legal_entity_still_forbidden(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-diff-le@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    assert biz.legal_entity_id != partner.legal_entity_id
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403
    assert join.json()["error"]["code"] in {"OWN_BUSINESS_OFFER", "SAME_USER_BUSINESS_MEMBER"}


@pytest.mark.asyncio
async def test_different_user_same_legal_entity_forbidden(client: AsyncClient, db: AsyncSession):
    await register_business(client, "le-owner@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    from tests.helpers import external_partner

    partner_client = await external_partner("le-clone@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile).order_by(PartnerProfile.id.desc()))).scalars().first()
    partner.legal_entity_id = biz.legal_entity_id
    await db.commit()
    join = await partner_client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403
    assert join.json()["error"]["code"] == "SAME_LEGAL_ENTITY"


@pytest.mark.asyncio
async def test_different_user_different_legal_entity_allowed(client: AsyncClient):
    await register_business(client, "ext-owner@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    partner = await partner_with_access(offer_id, "ext-partner@example.com")
    from tests.helpers import create_partner_link

    created = await create_partner_link(
        partner,
        offer_id,
        traffic_source="EMAIL",
        destination_url="https://acme.example.com/offer",
    )
    assert created["partner_id"] is not None


@pytest.mark.asyncio
async def test_self_partner_link_forbidden_even_with_planted_access(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-link@example.com")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _plant_access(db, int(offer_id), partner.id)
    created = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": int(offer_id), "name": "Self", "traffic_source": "email"},
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_self_partner_campaign_forbidden_even_with_planted_access(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-camp@example.com")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _plant_access(db, int(offer_id), partner.id)
    created = await client.post(
        "/api/v1/partner/campaigns",
        json={"offer_id": int(offer_id), "name": "Self campaign"},
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_commission_create_blocks_self_deal(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-comm@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    conversion = Conversion(
        business_id=biz.id,
        offer_id=int(offer_id),
        partner_id=partner.id,
        amount=Decimal("1000.00"),
        currency="RUB",
        commission_amount=Decimal("100.00"),
        status="approved",
        hold_period_days_snapshot=0,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(conversion)
    await db.flush()
    created = await create_commission_for_approved_conversion(db, conversion)
    assert created is None
    existing = await db.scalar(select(Commission).where(Commission.conversion_id == conversion.id))
    assert existing is None
    audit = (
        await db.execute(select(FinancialAuditEvent).where(FinancialAuditEvent.action == "SELF_PROMOTION_BLOCKED"))
    ).scalars().all()
    assert audit


@pytest.mark.asyncio
async def test_payout_excludes_historical_self_deal_commission(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-payout@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _eligible_partner(db, partner.id)
    commission = await _raw_available_commission(db, business_id=biz.id, partner_id=partner.id, offer_id=int(offer_id))
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        assert payouts == []
        await session.commit()
    await db.refresh(commission)
    assert commission.status == CommissionStatus.CANCELLED.value
    assert commission.reason == "SELF_PROMOTION_INVALID"


@pytest.mark.asyncio
async def test_business_owned_promotion_has_no_partner_commission(client: AsyncClient, db: AsyncSession):
    await register_business(client, "owned-promo@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    link = await client.post(
        f"/api/v1/business/offers/{offer_id}/links",
        json={"destination_url": "https://owned.example.com"},
    )
    assert link.status_code == 200
    assert link.json()["partner_id"] is None
    biz = (await db.execute(select(Business))).scalar_one()
    conversion = Conversion(
        business_id=biz.id,
        offer_id=int(offer_id),
        partner_id=None,
        amount=Decimal("1000.00"),
        currency="RUB",
        commission_amount=Decimal("100.00"),
        status="approved",
        hold_period_days_snapshot=0,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(conversion)
    await db.flush()
    assert await create_commission_for_approved_conversion(db, conversion) is None


@pytest.mark.asyncio
async def test_external_verified_profile_can_receive_payout(client: AsyncClient, db: AsyncSession):
    await register_business(client, "ok-pay@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    await partner_with_access(offer_id, "ok-pay-p@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _eligible_partner(db, partner.id)
    await _verify_legal_entity(db, biz.legal_entity_id)
    await _raw_available_commission(db, business_id=biz.id, partner_id=partner.id, offer_id=int(offer_id))
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        payouts = await generate_due_payouts(session, ignore_interval=True)
        await session.commit()
        assert len(payouts) == 1
        assert payouts[0].payer_business_id == biz.id
        assert payouts[0].partner_id == partner.id
        assert payouts[0].payout_profile_id is not None


@pytest.mark.asyncio
async def test_unverified_payout_profile_not_eligible(client: AsyncClient, db: AsyncSession):
    await register_user(client, "unv-p@example.com")
    await become_partner(client, "Unverified")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _eligible_partner(db, partner.id)
    profile = (
        await db.execute(select(PartnerPayoutProfile).where(PartnerPayoutProfile.partner_id == partner.id))
    ).scalar_one()
    profile.status = ProfileStatus.INCOMPLETE.value
    await db.commit()
    result = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert result.eligible is False
    assert result.reason_code == "PAYOUT_PROFILE_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_ordinary_individual_not_eligible(client: AsyncClient, db: AsyncSession):
    await register_user(client, "ord-p@example.com")
    await become_partner(client, "Ordinary")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _eligible_partner(db, partner.id, subject=LegalSubjectType.INDIVIDUAL, tax=TaxStatus.UNKNOWN)
    result = await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)
    assert result.eligible is False
    assert result.reason_code == "UNSUPPORTED_PARTNER_TYPE"


@pytest.mark.asyncio
async def test_npd_ip_and_legal_entity_eligible(client: AsyncClient, db: AsyncSession):
    await register_user(client, "types-p@example.com")
    await become_partner(client, "Types")
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    await _eligible_partner(db, partner.id, subject=LegalSubjectType.INDIVIDUAL, tax=TaxStatus.NPD)
    assert (await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)).eligible is True
    await _eligible_partner(db, partner.id, subject=LegalSubjectType.SOLE_PROPRIETOR)
    assert (await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)).eligible is True
    await _eligible_partner(db, partner.id, subject=LegalSubjectType.LEGAL_ENTITY)
    assert (await PartnerPayoutEligibilityService(db).check_payout_eligibility(partner.id)).eligible is True


@pytest.mark.asyncio
async def test_self_deal_guard_works_in_test_financial_mode(client: AsyncClient, db: AsyncSession):
    from app.core.config import settings

    assert settings.live_financial_transactions_allowed is False
    offer_id = await _dual_user_offer(client, "self-testmode@example.com")
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403


@pytest.mark.asyncio
async def test_business_member_cannot_promote_as_partner(client: AsyncClient, db: AsyncSession):
    await register_business(client, "member-owner@example.com")
    created = await client.post("/api/v1/business/offers", json=offer_payload(status="active"))
    offer_id = created.json()["id"]
    biz = (await db.execute(select(Business))).scalar_one()
    from tests.helpers import external_partner

    member = await external_partner("member-p@example.com", "Member Partner")
    user = (await db.execute(select(User).where(User.email == "member-p@example.com"))).scalar_one()
    db.add(BusinessMembership(business_id=biz.id, user_id=user.id, permission_role="manager", status="active"))
    await db.commit()
    join = await member.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 403
    assert join.json()["error"]["code"] in {"OWN_BUSINESS_OFFER", "SAME_USER_BUSINESS_MEMBER"}


@pytest.mark.asyncio
async def test_paid_invalid_payout_has_no_clawback(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-paid@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    commission = await _raw_available_commission(db, business_id=biz.id, partner_id=partner.id, offer_id=int(offer_id))
    payout = Payout(
        partner_id=partner.id,
        payer_business_id=biz.id,
        amount=Decimal("500.00"),
        currency="RUB",
        status=PayoutStatus.PAID.value,
        paid_at=datetime.now(timezone.utc),
        idempotency_key="self-paid-1",
    )
    db.add(payout)
    await db.flush()
    db.add(PayoutItem(payout_id=payout.id, commission_id=commission.id, amount=Decimal("500.00")))
    commission.status = CommissionStatus.PAID.value
    commission.active_payout_id = payout.id
    await db.commit()

    dry = await repair_self_promotion(db, execute=False)
    assert dry["dry_run"] is True
    assert dry["invalid_commissions"] >= 1
    await db.refresh(commission)
    assert commission.status == CommissionStatus.PAID.value

    executed = await repair_self_promotion(db, execute=True)
    await db.commit()
    await db.refresh(commission)
    await db.refresh(payout)
    assert commission.status == CommissionStatus.PAID.value
    assert payout.status == PayoutStatus.PAID.value
    assert executed["paid_review_payouts"] >= 1
    events = (
        await db.execute(
            select(FinancialAuditEvent).where(FinancialAuditEvent.action == "SELF_PROMOTION_INVALID_AFTER_PAYOUT")
        )
    ).scalars().all()
    assert events


@pytest.mark.asyncio
async def test_repair_dry_run_does_not_mutate(client: AsyncClient, db: AsyncSession):
    offer_id = await _dual_user_offer(client, "self-repair@example.com")
    biz = (await db.execute(select(Business))).scalar_one()
    partner = (await db.execute(select(PartnerProfile))).scalar_one()
    commission = await _raw_available_commission(db, business_id=biz.id, partner_id=partner.id, offer_id=int(offer_id))
    report = await repair_self_promotion(db, execute=False)
    assert report["dry_run"] is True
    await db.refresh(commission)
    assert commission.status == CommissionStatus.AVAILABLE.value
    executed = await repair_self_promotion(db, execute=True)
    await db.commit()
    await db.refresh(commission)
    assert executed["dry_run"] is False
    assert commission.status == CommissionStatus.CANCELLED.value
