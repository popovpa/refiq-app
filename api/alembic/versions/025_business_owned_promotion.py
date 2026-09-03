"""Business-owned campaigns and tracking links.

Revision ID: 025
Revises: 024
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNER_CHECK = (
    "(partner_id IS NOT NULL AND business_id IS NULL) "
    "OR (partner_id IS NULL AND business_id IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("business_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_campaigns_business_id", "campaigns", "businesses", ["business_id"], ["id"])
    op.create_index("ix_campaigns_business_id", "campaigns", ["business_id"])
    op.alter_column("campaigns", "partner_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_check_constraint("ck_campaigns_single_owner", "campaigns", OWNER_CHECK)

    op.add_column("tracking_links", sa.Column("business_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_tracking_links_business_id", "tracking_links", "businesses", ["business_id"], ["id"]
    )
    op.create_index("ix_tracking_links_business_id", "tracking_links", ["business_id"])
    op.alter_column("tracking_links", "partner_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_check_constraint("ck_tracking_links_single_owner", "tracking_links", OWNER_CHECK)

    op.add_column("clicks", sa.Column("partner_rqcid", sa.String(length=12), nullable=True))
    op.create_index("ix_clicks_partner_rqcid", "clicks", ["partner_rqcid"])

    op.add_column("conversions", sa.Column("partner_tracking_link_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_conversions_partner_tracking_link_id",
        "conversions",
        "tracking_links",
        ["partner_tracking_link_id"],
        ["id"],
    )
    op.create_index("ix_conversions_partner_tracking_link_id", "conversions", ["partner_tracking_link_id"])
    op.alter_column("conversions", "partner_id", existing_type=sa.BigInteger(), nullable=True)
    op.execute(
        sa.text(
            "UPDATE conversions SET partner_tracking_link_id = tracking_link_id "
            "WHERE partner_id IS NOT NULL AND tracking_link_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM conversions WHERE partner_id IS NULL"))
    op.execute(sa.text("DELETE FROM tracking_links WHERE partner_id IS NULL"))
    op.execute(sa.text("DELETE FROM campaigns WHERE partner_id IS NULL"))

    op.drop_constraint("fk_conversions_partner_tracking_link_id", "conversions", type_="foreignkey")
    op.drop_index("ix_conversions_partner_tracking_link_id", table_name="conversions")
    op.drop_column("conversions", "partner_tracking_link_id")
    op.alter_column("conversions", "partner_id", existing_type=sa.BigInteger(), nullable=False)

    op.drop_index("ix_clicks_partner_rqcid", table_name="clicks")
    op.drop_column("clicks", "partner_rqcid")

    op.drop_constraint("ck_tracking_links_single_owner", "tracking_links", type_="check")
    op.drop_constraint("fk_tracking_links_business_id", "tracking_links", type_="foreignkey")
    op.drop_index("ix_tracking_links_business_id", table_name="tracking_links")
    op.drop_column("tracking_links", "business_id")
    op.alter_column("tracking_links", "partner_id", existing_type=sa.BigInteger(), nullable=False)

    op.drop_constraint("ck_campaigns_single_owner", "campaigns", type_="check")
    op.drop_constraint("fk_campaigns_business_id", "campaigns", type_="foreignkey")
    op.drop_index("ix_campaigns_business_id", table_name="campaigns")
    op.drop_column("campaigns", "business_id")
    op.alter_column("campaigns", "partner_id", existing_type=sa.BigInteger(), nullable=False)
