"""Add Campaign.type for GENERAL auto-created campaigns.

Revision ID: 009
Revises: 008
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("type", sa.String(length=20), nullable=False, server_default="GENERAL"),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "type")
