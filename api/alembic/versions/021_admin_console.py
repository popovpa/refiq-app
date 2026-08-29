"""Admin users, admin audit, postback attempts, lookup indexes.

Revision ID: 021
Revises: 020
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("permissions", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_admin_users_email"),
    )
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)
    op.create_index("ix_admin_users_status", "admin_users", ["status"])

    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("admin_user_id", sa.BigInteger, sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admin_audit_events_admin_user_id", "admin_audit_events", ["admin_user_id"])
    op.create_index("ix_admin_audit_events_action", "admin_audit_events", ["action"])
    op.create_index("ix_admin_audit_events_created_at", "admin_audit_events", ["created_at"])
    op.create_index("ix_admin_audit_entity", "admin_audit_events", ["entity_type", "entity_id"])

    op.create_table(
        "postback_attempts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("rqcid", sa.String(length=12), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("conversion_id", sa.BigInteger, sa.ForeignKey("conversions.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_postback_attempts_business_id", "postback_attempts", ["business_id"])
    op.create_index("ix_postback_attempts_rqcid", "postback_attempts", ["rqcid"])
    op.create_index("ix_postback_attempts_received_at", "postback_attempts", ["received_at"])
    op.create_index("ix_postback_attempts_result", "postback_attempts", ["result"])
    op.create_index("ix_postback_attempts_conversion_id", "postback_attempts", ["conversion_id"])

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def _ensure_index(table: str, name: str, columns: list[str]) -> None:
        existing = {item["name"] for item in inspector.get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns)

    _ensure_index("clicks", "ix_clicks_created_at", ["created_at"])
    _ensure_index("clicks", "ix_clicks_tracking_link_id", ["tracking_link_id"])
    _ensure_index("conversions", "ix_conversions_created_at", ["created_at"])
    _ensure_index("conversions", "ix_conversions_business_id", ["business_id"])
    _ensure_index("conversions", "ix_conversions_partner_id", ["partner_id"])
    _ensure_index("sites", "ix_sites_domain", ["domain"])
    _ensure_index("sites", "ix_sites_business_id", ["business_id"])
    _ensure_index("offers", "ix_offers_status", ["status"])
    _ensure_index("offers", "ix_offers_business_id", ["business_id"])
    _ensure_index("businesses", "ix_businesses_status", ["status"])
    _ensure_index("tracking_links", "ix_tracking_links_offer_id", ["offer_id"])
    _ensure_index("tracking_links", "ix_tracking_links_partner_id", ["partner_id"])
    _ensure_index("commissions", "ix_commissions_status", ["status"])
    _ensure_index("commissions", "ix_commissions_partner_id", ["partner_id"])


def downgrade() -> None:
    op.drop_table("postback_attempts")
    op.drop_table("admin_audit_events")
    op.drop_table("admin_users")
