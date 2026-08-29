"""Align Campaign with product rules: description, ACTIVE/ARCHIVED.

Revision ID: 006
Revises: 005
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("description", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE campaigns
        SET description = destination_url_override
        WHERE destination_url_override IS NOT NULL AND destination_url_override <> ''
        """
    )
    op.drop_column("campaigns", "destination_url_override")
    op.execute("UPDATE campaigns SET status = 'ACTIVE' WHERE lower(status) IN ('active', 'paused')")
    op.execute("UPDATE campaigns SET status = 'ARCHIVED' WHERE lower(status) = 'archived'")
    op.alter_column(
        "campaigns",
        "status",
        existing_type=sa.String(20),
        server_default="ACTIVE",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.add_column("campaigns", sa.Column("destination_url_override", sa.String(500), nullable=True))
    op.execute("UPDATE campaigns SET destination_url_override = description")
    op.drop_column("campaigns", "description")
    op.execute("UPDATE campaigns SET status = 'active' WHERE status = 'ACTIVE'")
    op.execute("UPDATE campaigns SET status = 'archived' WHERE status = 'ARCHIVED'")
    op.alter_column(
        "campaigns",
        "status",
        existing_type=sa.String(20),
        server_default="active",
        existing_nullable=True,
    )
