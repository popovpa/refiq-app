"""Self-promotion repair fields: commission reason, payout profile, item exclusion.

Revision ID: 031
Revises: 030
Create Date: 2026-09-20

Existing financial rows are not deleted or rewritten. New columns are nullable.
Data correction is a separate dry-run/execute repair, not this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commissions", sa.Column("reason_code", sa.String(64), nullable=True))
    op.add_column("commissions", sa.Column("reason", sa.String(255), nullable=True))
    op.add_column("payouts", sa.Column("payout_profile_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_payouts_payout_profile_id",
        "payouts",
        "partner_payout_profiles",
        ["payout_profile_id"],
        ["id"],
    )
    op.add_column("payout_items", sa.Column("excluded_reason", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("payout_items", "excluded_reason")
    op.drop_constraint("fk_payouts_payout_profile_id", "payouts", type_="foreignkey")
    op.drop_column("payouts", "payout_profile_id")
    op.drop_column("commissions", "reason")
    op.drop_column("commissions", "reason_code")
