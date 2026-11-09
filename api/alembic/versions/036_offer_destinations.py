"""Offer landing pages and a nullable link reference.

Revision ID: 036
Revises: 035
Create Date: 2026-11-06

Additive only. Existing tracking links keep destination_url and short_code.
Legacy Product.url backfill is intentionally not part of this migration so the
DDL transaction stays short. Run backfill_legacy_destinations after the new
application code is deployed. The API also materializes one primary page for
an offer the first time its destinations are read.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offer_destinations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("offer_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_offer_destinations_status"),
        sa.CheckConstraint("type IN ('PRODUCT', 'CATEGORY', 'LANDING')", name="ck_offer_destinations_type"),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"], name="fk_offer_destinations_offer_id"),
        sa.UniqueConstraint("id", "offer_id", name="uq_offer_destinations_id_offer"),
        sa.UniqueConstraint("offer_id", "url", name="uq_offer_destinations_offer_url"),
    )
    op.create_index("ix_offer_destinations_offer_id", "offer_destinations", ["offer_id"])
    op.create_index("ix_offer_destinations_offer_status", "offer_destinations", ["offer_id", "status"])
    op.create_index(
        "uq_offer_destinations_one_primary",
        "offer_destinations",
        ["offer_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.add_column("tracking_links", sa.Column("offer_destination_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_tracking_links_offer_destination_id", "tracking_links", ["offer_destination_id"])
    op.create_foreign_key(
        "fk_tracking_links_destination_same_offer",
        "tracking_links",
        "offer_destinations",
        ["offer_destination_id", "offer_id"],
        ["id", "offer_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tracking_links_destination_same_offer", "tracking_links", type_="foreignkey")
    op.drop_index("ix_tracking_links_offer_destination_id", table_name="tracking_links")
    op.drop_column("tracking_links", "offer_destination_id")
    op.drop_index("uq_offer_destinations_one_primary", table_name="offer_destinations")
    op.drop_index("ix_offer_destinations_offer_status", table_name="offer_destinations")
    op.drop_index("ix_offer_destinations_offer_id", table_name="offer_destinations")
    op.drop_table("offer_destinations")
