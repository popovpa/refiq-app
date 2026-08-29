"""Postback credentials for business S2S authorization.

Revision ID: 011
Revises: 010
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "postback_credentials",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("business_id", sa.BigInteger, sa.ForeignKey("businesses.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("token_suffix", sa.String(length=4), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("postback_credentials")
