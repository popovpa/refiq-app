"""Financial foundation: LegalEntity, billing, payouts, ledger, audit.

Revision ID: 028
Revises: 027
Create Date: 2026-09-18

Downgrade drops financial tables and new columns. Historical financial
rows created after upgrade are removed; pre-028 domain data is preserved.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("tax_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("country", sa.String(3), nullable=False, server_default="RU"),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("middle_name", sa.String(100), nullable=True),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("ogrn", sa.String(15), nullable=True),
        sa.Column("ogrnip", sa.String(15), nullable=True),
        sa.Column("legal_address", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=True, server_default="DRAFT"),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_entities_inn", "legal_entities", ["inn"])
    op.create_index("ix_legal_entities_verification_status", "legal_entities", ["verification_status"])

    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("billing_period", sa.String(20), nullable=True, server_default="MONTHLY"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("effective_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version", name="uq_plan_version"),
    )
    op.create_index("ix_plan_versions_plan_id", "plan_versions", ["plan_id"])

    op.create_table(
        "terms_acceptances",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("legal_entity_id", sa.BigInteger(), sa.ForeignKey("legal_entities.id"), nullable=True),
        sa.Column("context", sa.String(20), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("document_version", sa.String(40), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "context", "document_type", "document_version", name="uq_terms_acceptance_user_doc"),
    )
    op.create_index("ix_terms_acceptances_user_id", "terms_acceptances", ["user_id"])
    op.create_index("ix_terms_acceptances_legal_entity_id", "terms_acceptances", ["legal_entity_id"])

    op.add_column("businesses", sa.Column("legal_entity_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_businesses_legal_entity_id", "businesses", "legal_entities", ["legal_entity_id"], ["id"])
    op.create_index("ix_businesses_legal_entity_id", "businesses", ["legal_entity_id"])

    op.add_column("partner_profiles", sa.Column("legal_entity_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_partner_profiles_legal_entity_id", "partner_profiles", "legal_entities", ["legal_entity_id"], ["id"])
    op.create_index("ix_partner_profiles_legal_entity_id", "partner_profiles", ["legal_entity_id"])

    op.create_table(
        "business_billing_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("legal_entity_id", sa.BigInteger(), sa.ForeignKey("legal_entities.id"), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True, server_default="TBANK"),
        sa.Column("provider_customer_id", sa.String(128), nullable=True),
        sa.Column("provider_account_id", sa.String(128), nullable=True),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=True, server_default="INCOMPLETE"),
        sa.Column("auto_payout_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id"),
    )
    op.create_index("ix_business_billing_profiles_legal_entity_id", "business_billing_profiles", ["legal_entity_id"])

    op.create_table(
        "partner_payout_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("partner_id", sa.BigInteger(), sa.ForeignKey("partner_profiles.id"), nullable=False),
        sa.Column("legal_entity_id", sa.BigInteger(), sa.ForeignKey("legal_entities.id"), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True, server_default="TBANK"),
        sa.Column("provider_recipient_id", sa.String(128), nullable=True),
        sa.Column("payout_method", sa.String(40), nullable=True, server_default="bank_transfer"),
        sa.Column("bank_account", sa.String(32), nullable=True),
        sa.Column("bank_bik", sa.String(12), nullable=True),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=True, server_default="INCOMPLETE"),
        sa.Column("verification_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partner_id"),
    )
    op.create_index("ix_partner_payout_profiles_legal_entity_id", "partner_payout_profiles", ["legal_entity_id"])

    op.add_column("business_subscriptions", sa.Column("plan_id", sa.BigInteger(), nullable=True))
    op.add_column("business_subscriptions", sa.Column("plan_version_id", sa.BigInteger(), nullable=True))
    op.add_column("business_subscriptions", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_subscriptions", sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_subscriptions", sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_subscriptions", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_subscriptions", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_business_subscriptions_plan_id", "business_subscriptions", "plans", ["plan_id"], ["id"])
    op.create_foreign_key("fk_business_subscriptions_plan_version_id", "business_subscriptions", "plan_versions", ["plan_version_id"], ["id"])
    op.create_index("ix_business_subscriptions_plan_id", "business_subscriptions", ["plan_id"])
    op.create_index("ix_business_subscriptions_plan_version_id", "business_subscriptions", ["plan_version_id"])

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("subscription_id", sa.BigInteger(), sa.ForeignKey("business_subscriptions.id"), nullable=True),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("plan_version_id", sa.BigInteger(), sa.ForeignKey("plan_versions.id"), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(20), nullable=True, server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_billing_invoices_idempotency"),
        sa.CheckConstraint("amount > 0", name="ck_billing_invoices_amount_positive"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_billing_invoices_currency_rub"),
    )
    op.create_index("ix_billing_invoices_business_id", "billing_invoices", ["business_id"])
    op.create_index("ix_billing_invoices_subscription_id", "billing_invoices", ["subscription_id"])
    op.create_index("ix_billing_invoices_plan_id", "billing_invoices", ["plan_id"])
    op.create_index("ix_billing_invoices_plan_version_id", "billing_invoices", ["plan_version_id"])
    op.create_index("ix_billing_invoices_status", "billing_invoices", ["status"])

    op.add_column("platform_fees", sa.Column("invoice_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_platform_fees_invoice_id", "platform_fees", "billing_invoices", ["invoice_id"], ["id"])
    op.create_index("ix_platform_fees_invoice_id", "platform_fees", ["invoice_id"])

    op.add_column("billing_transactions", sa.Column("invoice_id", sa.BigInteger(), nullable=True))
    op.add_column("billing_transactions", sa.Column("status", sa.String(32), nullable=True, server_default="created"))
    op.add_column("billing_transactions", sa.Column("provider", sa.String(32), nullable=True))
    op.add_column("billing_transactions", sa.Column("provider_transaction_id", sa.String(128), nullable=True))
    op.add_column("billing_transactions", sa.Column("provider_status", sa.String(40), nullable=True))
    op.add_column("billing_transactions", sa.Column("idempotency_key", sa.String(191), nullable=True))
    op.add_column("billing_transactions", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    op.create_foreign_key("fk_billing_transactions_invoice_id", "billing_transactions", "billing_invoices", ["invoice_id"], ["id"])
    op.create_index("ix_billing_transactions_invoice_id", "billing_transactions", ["invoice_id"])
    op.create_index("ix_billing_transactions_provider_transaction_id", "billing_transactions", ["provider_transaction_id"])
    op.create_unique_constraint("uq_billing_transactions_idempotency", "billing_transactions", ["idempotency_key"])

    op.add_column("offers", sa.Column("terms_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("offer_partner_access", sa.Column("offer_terms_version", sa.Integer(), nullable=True))
    op.add_column("offer_partner_access", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("conversions", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversions", sa.Column("reversed_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("conversions", sa.Column("reversal_reason", sa.String(40), nullable=True))
    op.add_column("conversions", sa.Column("reversal_comment", sa.String(1000), nullable=True))
    op.create_foreign_key("fk_conversions_reversed_by_user_id", "conversions", "users", ["reversed_by_user_id"], ["id"])
    op.create_index("ix_conversions_reversed_by_user_id", "conversions", ["reversed_by_user_id"])

    op.add_column("commissions", sa.Column("offer_id", sa.BigInteger(), nullable=True))
    op.add_column("commissions", sa.Column("business_legal_entity_id", sa.BigInteger(), nullable=True))
    op.add_column("commissions", sa.Column("partner_legal_entity_id", sa.BigInteger(), nullable=True))
    op.add_column("commissions", sa.Column("commission_type", sa.String(20), nullable=True))
    op.add_column("commissions", sa.Column("commission_value", sa.Numeric(12, 4), nullable=True))
    op.add_column("commissions", sa.Column("calculation_base", sa.Numeric(14, 2), nullable=True))
    op.add_column("commissions", sa.Column("calculation_version", sa.String(20), nullable=True, server_default="v1"))
    op.add_column("commissions", sa.Column("offer_terms_version", sa.Integer(), nullable=True))
    op.add_column("commissions", sa.Column("hold_period_days", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("commissions", sa.Column("active_payout_id", sa.BigInteger(), nullable=True))
    op.add_column("commissions", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_commissions_offer_id", "commissions", "offers", ["offer_id"], ["id"])
    op.create_foreign_key("fk_commissions_business_legal_entity_id", "commissions", "legal_entities", ["business_legal_entity_id"], ["id"])
    op.create_foreign_key("fk_commissions_partner_legal_entity_id", "commissions", "legal_entities", ["partner_legal_entity_id"], ["id"])
    op.create_index("ix_commissions_offer_id", "commissions", ["offer_id"])
    op.create_index("ix_commissions_business_legal_entity_id", "commissions", ["business_legal_entity_id"])
    op.create_index("ix_commissions_partner_legal_entity_id", "commissions", ["partner_legal_entity_id"])
    op.create_index("ix_commissions_active_payout_id", "commissions", ["active_payout_id"])
    op.create_unique_constraint("uq_commission_conversion", "commissions", ["conversion_id"])

    op.add_column("payouts", sa.Column("payer_business_id", sa.BigInteger(), nullable=True))
    op.add_column("payouts", sa.Column("payer_legal_entity_id", sa.BigInteger(), nullable=True))
    op.add_column("payouts", sa.Column("recipient_legal_entity_id", sa.BigInteger(), nullable=True))
    op.add_column("payouts", sa.Column("provider", sa.String(32), nullable=True, server_default="TBANK"))
    op.add_column("payouts", sa.Column("provider_transaction_id", sa.String(128), nullable=True))
    op.add_column("payouts", sa.Column("provider_status", sa.String(40), nullable=True))
    op.add_column("payouts", sa.Column("failure_class", sa.String(64), nullable=True))
    op.add_column("payouts", sa.Column("failure_message", sa.String(500), nullable=True))
    op.add_column("payouts", sa.Column("idempotency_key", sa.String(191), nullable=True))
    op.add_column("payouts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("payouts", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payouts", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payouts", sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payouts", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_payouts_payer_business_id", "payouts", "businesses", ["payer_business_id"], ["id"])
    op.create_foreign_key("fk_payouts_payer_legal_entity_id", "payouts", "legal_entities", ["payer_legal_entity_id"], ["id"])
    op.create_foreign_key("fk_payouts_recipient_legal_entity_id", "payouts", "legal_entities", ["recipient_legal_entity_id"], ["id"])
    op.create_index("ix_payouts_payer_business_id", "payouts", ["payer_business_id"])
    op.create_index("ix_payouts_payer_legal_entity_id", "payouts", ["payer_legal_entity_id"])
    op.create_index("ix_payouts_recipient_legal_entity_id", "payouts", ["recipient_legal_entity_id"])
    op.create_index("ix_payouts_provider_transaction_id", "payouts", ["provider_transaction_id"])
    op.create_index("ix_payouts_status", "payouts", ["status"])
    op.create_unique_constraint("uq_payouts_idempotency", "payouts", ["idempotency_key"])
    op.create_check_constraint("ck_payouts_amount_positive", "payouts", "amount > 0")
    op.create_check_constraint("ck_payouts_currency_rub", "payouts", "currency = 'RUB'")
    op.create_foreign_key("fk_commissions_active_payout_id", "commissions", "payouts", ["active_payout_id"], ["id"])
    op.alter_column("payouts", "status", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True)
    op.alter_column("commissions", "status", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True)
    op.alter_column("conversions", "status", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True)
    op.alter_column(
        "business_subscriptions", "status", existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True
    )
    op.create_unique_constraint("uq_payout_item_commission", "payout_items", ["payout_id", "commission_id"])

    op.create_table(
        "financial_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("partner_id", sa.BigInteger(), sa.ForeignKey("partner_profiles.id"), nullable=True),
        sa.Column("legal_entity_id", sa.BigInteger(), sa.ForeignKey("legal_entities.id"), nullable=True),
        sa.Column("operation_type", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(50), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_entries_scope", "financial_entries", ["scope"])
    op.create_index("ix_financial_entries_operation_type", "financial_entries", ["operation_type"])
    op.create_index("ix_financial_entries_business_id", "financial_entries", ["business_id"])
    op.create_index("ix_financial_entries_partner_id", "financial_entries", ["partner_id"])
    op.create_index("ix_financial_entries_legal_entity_id", "financial_entries", ["legal_entity_id"])

    op.create_table(
        "financial_audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("system_actor", sa.String(80), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("old_status", sa.String(40), nullable=True),
        sa.Column("new_status", sa.String(40), nullable=True),
        sa.Column("reason", sa.String(120), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_audit_events_action", "financial_audit_events", ["action"])
    op.create_index("ix_financial_audit_events_actor_user_id", "financial_audit_events", ["actor_user_id"])

    op.create_table(
        "financial_idempotency_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(191), nullable=False),
        sa.Column("operation_type", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "provider_webhook_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=True),
        sa.Column("provider_status", sa.String(40), nullable=True),
        sa.Column("payload_digest", sa.String(64), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_provider_webhook_event"),
    )

    op.create_table(
        "financial_job_locks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_name", sa.String(80), nullable=False),
        sa.Column("run_key", sa.String(80), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_name", "run_key", name="uq_financial_job_lock"),
    )

    op.create_table(
        "partner_traffic_suspensions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("payout_id", sa.BigInteger(), sa.ForeignKey("payouts.id"), nullable=True),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_partner_traffic_suspension_business"),
    )
    op.create_index("ix_partner_traffic_suspensions_payout_id", "partner_traffic_suspensions", ["payout_id"])

    op.create_table(
        "test_financial_operations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("provider_transaction_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_transaction_id"),
    )

    op.execute(
        """
        INSERT INTO plans (code, name, billing_period, is_active)
        VALUES ('pro', 'Pro', 'MONTHLY', true)
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO plan_versions (plan_id, version, amount, currency)
        SELECT id, 1, 4990.00, 'RUB' FROM plans WHERE code = 'pro'
        AND NOT EXISTS (SELECT 1 FROM plan_versions pv WHERE pv.plan_id = plans.id)
        """
    )
    op.execute(
        """
        INSERT INTO legal_entities (subject_type, tax_status, country, legal_name, verification_status)
        SELECT 'LEGAL_ENTITY', 'UNKNOWN', COALESCE(country, 'RU'), COALESCE(legal_name, name), 'DRAFT'
        FROM businesses WHERE legal_entity_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE businesses b SET legal_entity_id = le.id
        FROM legal_entities le
        WHERE b.legal_entity_id IS NULL
          AND le.legal_name = COALESCE(b.legal_name, b.name)
          AND le.country = COALESCE(b.country, 'RU')
          AND le.subject_type = 'LEGAL_ENTITY'
        """
    )
    op.execute(
        """
        INSERT INTO legal_entities (subject_type, tax_status, country, legal_name, verification_status)
        SELECT 'INDIVIDUAL', 'UNKNOWN', 'RU', display_name, 'DRAFT'
        FROM partner_profiles WHERE legal_entity_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE partner_profiles p SET legal_entity_id = le.id
        FROM legal_entities le
        WHERE p.legal_entity_id IS NULL
          AND le.legal_name IS NOT DISTINCT FROM p.display_name
          AND le.subject_type = 'INDIVIDUAL'
        """
    )
    op.execute(
        """
        INSERT INTO business_billing_profiles (business_id, legal_entity_id, provider, status)
        SELECT id, legal_entity_id, 'TBANK', 'INCOMPLETE' FROM businesses
        WHERE id NOT IN (SELECT business_id FROM business_billing_profiles)
        """
    )
    op.execute(
        """
        INSERT INTO partner_payout_profiles (partner_id, legal_entity_id, provider, payout_method, status)
        SELECT id, legal_entity_id, 'TBANK', 'bank_transfer', 'INCOMPLETE' FROM partner_profiles
        WHERE id NOT IN (SELECT partner_id FROM partner_payout_profiles)
        """
    )
    op.execute(
        """
        UPDATE commissions SET status = 'hold'
        WHERE status = 'approved' AND available_at IS NOT NULL AND available_at > NOW()
        """
    )
    op.execute(
        """
        UPDATE commissions SET status = 'available'
        WHERE status IN ('approved', 'payable')
        """
    )
    op.execute(
        """
        UPDATE payouts SET status = 'awaiting_confirmation' WHERE status = 'pending'
        """
    )
    op.execute(
        """
        UPDATE business_subscriptions
        SET status = 'trial',
            trial_ends_at = COALESCE(started_at, NOW()) + INTERVAL '14 days',
            current_period_start = started_at,
            current_period_end = COALESCE(started_at, NOW()) + INTERVAL '14 days'
        WHERE status = 'active' AND plan IN ('free', 'pro')
        """
    )


def downgrade() -> None:
    # Destructive for financial history created after 028. Domain tables stay.
    op.drop_table("test_financial_operations")
    op.drop_table("partner_traffic_suspensions")
    op.drop_table("financial_job_locks")
    op.drop_table("provider_webhook_events")
    op.drop_table("financial_idempotency_keys")
    op.drop_table("financial_audit_events")
    op.drop_table("financial_entries")
    op.drop_constraint("fk_commissions_active_payout_id", "commissions", type_="foreignkey")
    op.drop_constraint("uq_payout_item_commission", "payout_items", type_="unique")
    op.drop_constraint("ck_payouts_currency_rub", "payouts", type_="check")
    op.drop_constraint("ck_payouts_amount_positive", "payouts", type_="check")
    op.drop_constraint("uq_payouts_idempotency", "payouts", type_="unique")
    for col in (
        "payer_business_id",
        "payer_legal_entity_id",
        "recipient_legal_entity_id",
        "provider",
        "provider_transaction_id",
        "provider_status",
        "failure_class",
        "failure_message",
        "idempotency_key",
        "version",
        "due_at",
        "confirmed_at",
        "processing_at",
        "failed_at",
    ):
        op.drop_column("payouts", col)
    op.drop_constraint("uq_commission_conversion", "commissions", type_="unique")
    for col in (
        "offer_id",
        "business_legal_entity_id",
        "partner_legal_entity_id",
        "commission_type",
        "commission_value",
        "calculation_base",
        "calculation_version",
        "offer_terms_version",
        "hold_period_days",
        "active_payout_id",
        "reversed_at",
    ):
        op.drop_column("commissions", col)
    op.drop_column("conversions", "reversal_comment")
    op.drop_column("conversions", "reversal_reason")
    op.drop_column("conversions", "reversed_by_user_id")
    op.drop_column("conversions", "reversed_at")
    op.drop_column("offer_partner_access", "terms_accepted_at")
    op.drop_column("offer_partner_access", "offer_terms_version")
    op.drop_column("offers", "terms_version")
    op.drop_constraint("uq_billing_transactions_idempotency", "billing_transactions", type_="unique")
    for col in ("invoice_id", "status", "provider", "provider_transaction_id", "provider_status", "idempotency_key", "updated_at"):
        op.drop_column("billing_transactions", col)
    op.drop_column("platform_fees", "invoice_id")
    op.drop_table("billing_invoices")
    for col in ("plan_id", "plan_version_id", "trial_ends_at", "grace_ends_at", "current_period_start", "current_period_end", "cancelled_at"):
        op.drop_column("business_subscriptions", col)
    op.drop_table("partner_payout_profiles")
    op.drop_table("business_billing_profiles")
    op.drop_column("partner_profiles", "legal_entity_id")
    op.drop_column("businesses", "legal_entity_id")
    op.drop_table("terms_acceptances")
    op.drop_table("plan_versions")
    op.drop_table("plans")
    op.drop_table("legal_entities")
