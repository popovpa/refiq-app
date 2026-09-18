from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import EntityId, fk_column, pk_column

MONEY = Numeric(14, 2)


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id: Mapped[int] = pk_column()
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    country: Mapped[str] = mapped_column(String(3), nullable=False, default="RU")
    legal_name: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    ogrn: Mapped[str | None] = mapped_column(String(15))
    ogrnip: Mapped[str | None] = mapped_column(String(15))
    legal_address: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    verification_source: Mapped[str | None] = mapped_column(String(32), index=True)
    verification_reason: Mapped[str | None] = mapped_column(Text)
    verification_reason_code: Mapped[str | None] = mapped_column(String(64))
    verified_by_admin_id: Mapped[int | None] = mapped_column(EntityId, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LegalEntityVerificationAttempt(Base):
    __tablename__ = "legal_entity_verification_attempts"

    id: Mapped[int] = pk_column()
    legal_entity_id: Mapped[int] = fk_column("legal_entities.id")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_admin_id: Mapped[int | None] = mapped_column(EntityId, nullable=True, index=True)
    actor_user_id: Mapped[int | None] = fk_column("users.id", nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    public_reason: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)


class TermsAcceptance(Base):
    __tablename__ = "terms_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "context",
            "document_type",
            "document_version",
            name="uq_terms_acceptance_user_doc",
        ),
    )

    id: Mapped[int] = pk_column()
    user_id: Mapped[int] = fk_column("users.id")
    legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    context: Mapped[str] = mapped_column(String(20), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    document_version: Mapped[str] = mapped_column(String(40), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))


class BusinessBillingProfile(Base):
    __tablename__ = "business_billing_profiles"

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id", unique=True)
    legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="TBANK")
    provider_customer_id: Mapped[str | None] = mapped_column(String(128))
    provider_account_id: Mapped[str | None] = mapped_column(String(128))
    billing_email: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="INCOMPLETE")
    auto_payout_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PartnerPayoutProfile(Base):
    __tablename__ = "partner_payout_profiles"

    id: Mapped[int] = pk_column()
    partner_id: Mapped[int] = fk_column("partner_profiles.id", unique=True)
    legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="TBANK")
    provider_recipient_id: Mapped[str | None] = mapped_column(String(128))
    payout_method: Mapped[str] = mapped_column(String(40), default="bank_transfer")
    bank_account: Mapped[str | None] = mapped_column(String(32))
    bank_bik: Mapped[str | None] = mapped_column(String(12))
    bank_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="INCOMPLETE")
    verification_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = pk_column()
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(20), default="MONTHLY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (UniqueConstraint("plan_id", "version", name="uq_plan_version"),)

    id: Mapped[int] = pk_column()
    plan_id: Mapped[int] = fk_column("plans.id")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_billing_invoices_amount_positive"),
        CheckConstraint("currency = 'RUB'", name="ck_billing_invoices_currency_rub"),
        UniqueConstraint("idempotency_key", name="uq_billing_invoices_idempotency"),
    )

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id")
    subscription_id: Mapped[int | None] = fk_column("business_subscriptions.id", nullable=True)
    plan_id: Mapped[int | None] = fk_column("plans.id", nullable=True)
    plan_version_id: Mapped[int | None] = fk_column("plan_versions.id", nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialEntry(Base):
    __tablename__ = "financial_entries"

    id: Mapped[int] = pk_column()
    scope: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    business_id: Mapped[int | None] = fk_column("businesses.id", nullable=True)
    partner_id: Mapped[int | None] = fk_column("partner_profiles.id", nullable=True)
    legal_entity_id: Mapped[int | None] = fk_column("legal_entities.id", nullable=True)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialAuditEvent(Base):
    __tablename__ = "financial_audit_events"

    id: Mapped[int] = pk_column()
    actor_user_id: Mapped[int | None] = fk_column("users.id", nullable=True)
    system_actor: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(120))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialIdempotencyKey(Base):
    __tablename__ = "financial_idempotency_keys"

    id: Mapped[int] = pk_column()
    key: Mapped[str] = mapped_column(String(191), unique=True, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderWebhookEvent(Base):
    __tablename__ = "provider_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "external_event_id", name="uq_provider_webhook_event"),)

    id: Mapped[int] = pk_column()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(80))
    provider_status: Mapped[str | None] = mapped_column(String(40))
    payload_digest: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialJobLock(Base):
    __tablename__ = "financial_job_locks"

    id: Mapped[int] = pk_column()
    job_name: Mapped[str] = mapped_column(String(80), nullable=False)
    run_key: Mapped[str] = mapped_column(String(80), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("job_name", "run_key", name="uq_financial_job_lock"),)


class PartnerTrafficSuspension(Base):
    __tablename__ = "partner_traffic_suspensions"
    __table_args__ = (UniqueConstraint("business_id", name="uq_partner_traffic_suspension_business"),)

    id: Mapped[int] = pk_column()
    business_id: Mapped[int] = fk_column("businesses.id", unique=True)
    payout_id: Mapped[int | None] = fk_column("payouts.id", nullable=True)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestFinancialOperation(Base):
    __tablename__ = "test_financial_operations"

    id: Mapped[int] = pk_column()
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
