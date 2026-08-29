"""Creatives, brand kits, assets, and AI generation lifecycle.

Revision ID: 017
Revises: 016
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assets_storage_key", "assets", ["storage_key"], unique=True)

    op.create_table(
        "brand_kits",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("logo_asset_id", sa.BigInteger, sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("brand_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tone_of_voice", sa.Text, nullable=True),
        sa.Column("product_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("allowed_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("forbidden_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mandatory_disclaimers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brand_kits_business_id", "brand_kits", ["business_id"], unique=True)
    op.create_index("ix_brand_kits_logo_asset_id", "brand_kits", ["logo_asset_id"])

    op.create_table(
        "creatives",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=True),
        sa.Column("campaign_id", sa.BigInteger, sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("text_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("asset_id", sa.BigInteger, sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=True),
        sa.Column("format", sa.String(length=40), nullable=True),
        sa.Column("generation_id", sa.String(length=36), nullable=True),
        sa.Column("selected_variant", sa.String(length=40), nullable=True),
        sa.Column("policy_status", sa.String(length=20), nullable=True),
        sa.Column("policy_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_creatives_offer_id", "creatives", ["offer_id"])
    op.create_index("ix_creatives_created_by_user_id", "creatives", ["created_by_user_id"])
    op.create_index("ix_creatives_partner_id", "creatives", ["partner_id"])
    op.create_index("ix_creatives_campaign_id", "creatives", ["campaign_id"])
    op.create_index("ix_creatives_asset_id", "creatives", ["asset_id"])
    op.create_index("ix_creatives_status", "creatives", ["status"])
    op.create_index("ix_creatives_generation_id", "creatives", ["generation_id"])

    op.create_table(
        "ai_generations",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("generation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=True),
        sa.Column("creative_id", sa.BigInteger, sa.ForeignKey("creatives.id"), nullable=True),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("generated_variants", sa.Integer, nullable=True),
        sa.Column("selected_variant", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_generations_generation_id", "ai_generations", ["generation_id"], unique=True)
    op.create_index("ix_ai_generations_user_id", "ai_generations", ["user_id"])
    op.create_index("ix_ai_generations_offer_id", "ai_generations", ["offer_id"])
    op.create_index("ix_ai_generations_creative_id", "ai_generations", ["creative_id"])
    op.create_index("ix_ai_generations_status", "ai_generations", ["status"])

    op.add_column("ai_usage", sa.Column("asset_count", sa.Integer, nullable=True))
    op.add_column("ai_usage", sa.Column("image_width", sa.Integer, nullable=True))
    op.add_column("ai_usage", sa.Column("image_height", sa.Integer, nullable=True))
    op.add_column("ai_usage", sa.Column("image_format", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_usage", "image_format")
    op.drop_column("ai_usage", "image_height")
    op.drop_column("ai_usage", "image_width")
    op.drop_column("ai_usage", "asset_count")
    op.drop_index("ix_ai_generations_status", table_name="ai_generations")
    op.drop_index("ix_ai_generations_creative_id", table_name="ai_generations")
    op.drop_index("ix_ai_generations_offer_id", table_name="ai_generations")
    op.drop_index("ix_ai_generations_user_id", table_name="ai_generations")
    op.drop_index("ix_ai_generations_generation_id", table_name="ai_generations")
    op.drop_table("ai_generations")
    op.drop_index("ix_creatives_generation_id", table_name="creatives")
    op.drop_index("ix_creatives_status", table_name="creatives")
    op.drop_index("ix_creatives_asset_id", table_name="creatives")
    op.drop_index("ix_creatives_campaign_id", table_name="creatives")
    op.drop_index("ix_creatives_partner_id", table_name="creatives")
    op.drop_index("ix_creatives_created_by_user_id", table_name="creatives")
    op.drop_index("ix_creatives_offer_id", table_name="creatives")
    op.drop_table("creatives")
    op.drop_index("ix_brand_kits_logo_asset_id", table_name="brand_kits")
    op.drop_index("ix_brand_kits_business_id", table_name="brand_kits")
    op.drop_table("brand_kits")
    op.drop_index("ix_assets_storage_key", table_name="assets")
    op.drop_table("assets")
