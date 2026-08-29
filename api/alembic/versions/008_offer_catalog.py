"""Offer catalog fields, partner application details, link metadata, clicks.

Revision ID: 008
Revises: 007
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("category", sa.String(length=80), nullable=True))
    op.add_column("offers", sa.Column("geo", sa.String(length=255), nullable=True))
    op.add_column("offers", sa.Column("allowed_traffic", sa.JSON(), nullable=True))
    op.add_column("offers", sa.Column("forbidden_traffic", sa.JSON(), nullable=True))
    op.add_column("offers", sa.Column("partner_notes", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("materials", sa.JSON(), nullable=True))

    op.add_column("offer_partner_access", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("offer_partner_access", sa.Column("traffic_sources", sa.JSON(), nullable=True))
    op.add_column("offer_partner_access", sa.Column("topics", sa.String(length=255), nullable=True))
    op.add_column("offer_partner_access", sa.Column("geo", sa.String(length=255), nullable=True))

    op.add_column("tracking_links", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("tracking_links", sa.Column("traffic_source", sa.String(length=80), nullable=True))
    op.add_column("tracking_links", sa.Column("notes", sa.Text(), nullable=True))

    op.create_table(
        "clicks",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("tracking_link_id", sa.BigInteger, sa.ForeignKey("tracking_links.id"), nullable=False, index=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.BigInteger, sa.ForeignKey("partner_profiles.id"), nullable=False, index=True),
        sa.Column("rqcid", sa.String(length=12), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.execute(
        """
        UPDATE offers
        SET category = COALESCE(category, 'SaaS'),
            geo = COALESCE(geo, 'RU'),
            allowed_traffic = COALESCE(allowed_traffic, '["seo","content","social","telegram"]'::json),
            forbidden_traffic = COALESCE(forbidden_traffic, '[]'::json)
        """
    )


def downgrade() -> None:
    op.drop_table("clicks")
    op.drop_column("tracking_links", "notes")
    op.drop_column("tracking_links", "traffic_source")
    op.drop_column("tracking_links", "name")
    op.drop_column("offer_partner_access", "geo")
    op.drop_column("offer_partner_access", "topics")
    op.drop_column("offer_partner_access", "traffic_sources")
    op.drop_column("offer_partner_access", "comment")
    op.drop_column("offers", "materials")
    op.drop_column("offers", "partner_notes")
    op.drop_column("offers", "forbidden_traffic")
    op.drop_column("offers", "allowed_traffic")
    op.drop_column("offers", "geo")
    op.drop_column("offers", "category")
    op.drop_column("offers", "image_url")
