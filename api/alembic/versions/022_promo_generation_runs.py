"""Offer promo generation runs and items.

Revision ID: 022
Revises: 021
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offer_promo_generation_runs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("offer_id", sa.BigInteger, sa.ForeignKey("offers.id"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("total_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cancelled_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("offer_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("promotion_brief", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_offer_promo_generation_runs_offer_id", "offer_promo_generation_runs", ["offer_id"])
    op.create_index("ix_offer_promo_generation_runs_status", "offer_promo_generation_runs", ["status"])
    op.create_index(
        "ix_offer_promo_generation_runs_offer_status",
        "offer_promo_generation_runs",
        ["offer_id", "status"],
    )

    op.create_table(
        "offer_promo_generation_items",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "generation_run_id",
            sa.BigInteger,
            sa.ForeignKey("offer_promo_generation_runs.id"),
            nullable=False,
        ),
        sa.Column("material_type", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("promo_material_id", sa.BigInteger, sa.ForeignKey("creatives.id"), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_offer_promo_generation_items_run_id",
        "offer_promo_generation_items",
        ["generation_run_id"],
    )
    op.create_index("ix_offer_promo_generation_items_status", "offer_promo_generation_items", ["status"])
    op.create_index(
        "ix_offer_promo_generation_items_run_status",
        "offer_promo_generation_items",
        ["generation_run_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_offer_promo_generation_items_run_status", table_name="offer_promo_generation_items")
    op.drop_index("ix_offer_promo_generation_items_status", table_name="offer_promo_generation_items")
    op.drop_index("ix_offer_promo_generation_items_run_id", table_name="offer_promo_generation_items")
    op.drop_table("offer_promo_generation_items")
    op.drop_index("ix_offer_promo_generation_runs_offer_status", table_name="offer_promo_generation_runs")
    op.drop_index("ix_offer_promo_generation_runs_status", table_name="offer_promo_generation_runs")
    op.drop_index("ix_offer_promo_generation_runs_offer_id", table_name="offer_promo_generation_runs")
    op.drop_table("offer_promo_generation_runs")
