"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("phone", sa.String(50)),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "role", name="uq_user_role"),
    )

    op.create_table(
        "businesses",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255)),
        sa.Column("country", sa.String(3)),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "business_memberships",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("permission_role", sa.String(20), server_default="owner"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "user_id", name="uq_business_membership"),
    )

    op.create_table(
        "partner_profiles",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("description", sa.String(1000)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "business_partners",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "partner_id", name="uq_business_partner"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("url", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "offers",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("destination_url", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("visibility", sa.String(20), server_default="public"),
        sa.Column("access_policy", sa.String(20), server_default="open"),
        sa.Column("conversion_type", sa.String(20), server_default="sale"),
        sa.Column("attribution_window_days", sa.Integer, server_default="30"),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "offer_commission_rules",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("currency", sa.String(3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "offer_partner_access",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("source", sa.String(20), server_default="marketplace"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("offer_id", "partner_id", name="uq_offer_partner_access"),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("destination_url_override", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tracking_links",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("campaign_id", sa.BigInteger, sa.ForeignKey("campaigns.id"), index=True),
        sa.Column("short_code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("destination_url_override", sa.String(500)),
        sa.Column("source", sa.String(100)),
        sa.Column("sub1", sa.String(255)),
        sa.Column("sub2", sa.String(255)),
        sa.Column("sub3", sa.String(255)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conversions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("tracking_link_id", sa.BigInteger, sa.ForeignKey("tracking_links.id"), index=True),
        sa.Column("click_id", sa.String(100), index=True),
        sa.Column("external_id", sa.String(255), index=True),
        sa.Column("amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("commission_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending", index=True),
        sa.Column("converted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "commissions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("conversion_id", sa.BigInteger, sa.ForeignKey("conversions.id"), nullable=False, index=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "payouts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "payout_items",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("payout_id", sa.BigInteger, sa.ForeignKey("payouts.id"), nullable=False, index=True),
        sa.Column("commission_id", sa.BigInteger, sa.ForeignKey("commissions.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )

    op.create_table(
        "business_subscriptions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "platform_fees",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("fee_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "billing_transactions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB"),
        sa.Column("reference_type", sa.String(50)),
        sa.Column("reference_id", sa.String(50)),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_settings",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "business_settings",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), unique=True, nullable=False),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "partner_settings",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), unique=True, nullable=False),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), index=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(50)),
        sa.Column("details", postgresql.JSONB),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("aggregate_type", sa.String(50)),
        sa.Column("aggregate_id", sa.String(50)),
        sa.Column("payload", postgresql.JSONB, server_default="{}"),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("audit_logs")
    op.drop_table("partner_settings")
    op.drop_table("business_settings")
    op.drop_table("user_settings")
    op.drop_table("billing_transactions")
    op.drop_table("platform_fees")
    op.drop_table("business_subscriptions")
    op.drop_table("payout_items")
    op.drop_table("payouts")
    op.drop_table("commissions")
    op.drop_table("conversions")
    op.drop_table("tracking_links")
    op.drop_table("campaigns")
    op.drop_table("offer_partner_access")
    op.drop_table("offer_commission_rules")
    op.drop_table("offers")
    op.drop_table("products")
    op.drop_table("business_partners")
    op.drop_table("partner_profiles")
    op.drop_table("business_memberships")
    op.drop_table("businesses")
    op.drop_table("user_roles")
    op.drop_table("users")
