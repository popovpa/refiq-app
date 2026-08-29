"""JS SDK script identifiers for business connections.

Revision ID: 015
Revises: 014
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sdk_scripts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, unique=True, index=True),
        sa.Column("script_id", sa.String(length=5), nullable=False, unique=True, index=True),
        sa.Column("created_by_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sdk_scripts")
