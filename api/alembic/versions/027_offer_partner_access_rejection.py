"""Add rejection reason to partner offer access.

Revision ID: 027
Revises: 026
Create Date: 2026-09-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offer_partner_access", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("offer_partner_access", sa.Column("business_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("offer_partner_access", "business_comment")
    op.drop_column("offer_partner_access", "rejection_reason")
