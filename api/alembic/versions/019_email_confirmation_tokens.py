"""Email confirmation tokens.

Revision ID: 019
Revises: 018
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_confirmation_tokens",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_confirmation_tokens_token_hash",
        "email_confirmation_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_email_confirmation_tokens_user_id", "email_confirmation_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_email_confirmation_tokens_user_id", table_name="email_confirmation_tokens")
    op.drop_index("ix_email_confirmation_tokens_token_hash", table_name="email_confirmation_tokens")
    op.drop_table("email_confirmation_tokens")
