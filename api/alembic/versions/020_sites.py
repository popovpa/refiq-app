"""Sites belonging to a business; SDK script is per site.

Revision ID: 020
Revises: 019
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("site_key", sa.String(length=5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("business_id", "domain", name="uq_site_business_domain"),
    )
    op.create_index("ix_sites_site_key", "sites", ["site_key"], unique=True)

    op.add_column(
        "sdk_scripts",
        sa.Column("site_id", sa.BigInteger, sa.ForeignKey("sites.id"), nullable=True),
    )
    op.create_index("ix_sdk_scripts_site_id", "sdk_scripts", ["site_id"], unique=True)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_names = {item["name"] for item in inspector.get_unique_constraints("sdk_scripts")}
    if "sdk_scripts_business_id_key" in unique_names:
        op.drop_constraint("sdk_scripts_business_id_key", "sdk_scripts", type_="unique")
    indexes = {item["name"]: item for item in inspector.get_indexes("sdk_scripts")}
    business_index = indexes.get("ix_sdk_scripts_business_id")
    if business_index and business_index.get("unique"):
        op.drop_index("ix_sdk_scripts_business_id", table_name="sdk_scripts")
        op.create_index("ix_sdk_scripts_business_id", "sdk_scripts", ["business_id"], unique=False)

    from app.modules.sites.backfill import backfill_sites

    backfill_sites(bind)


def downgrade() -> None:
    op.drop_index("ix_sdk_scripts_site_id", table_name="sdk_scripts")
    op.drop_column("sdk_scripts", "site_id")
    op.drop_index("ix_sites_site_key", table_name="sites")
    op.drop_table("sites")
    op.create_index("ix_sdk_scripts_business_id", "sdk_scripts", ["business_id"], unique=True)
