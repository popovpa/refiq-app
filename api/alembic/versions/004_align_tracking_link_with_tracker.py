"""Align tracking_links with tracker TrackingLink.

Revision ID: 004
Revises: 003
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE tracking_links SET status = 'ACTIVE' WHERE lower(status) = 'active'")
    op.execute("UPDATE tracking_links SET status = 'DISABLED' WHERE lower(status) IN ('disabled', 'inactive')")
    op.alter_column(
        "tracking_links",
        "status",
        existing_type=sa.String(20),
        server_default="ACTIVE",
        existing_nullable=True,
    )
    op.drop_column("tracking_links", "source")
    op.drop_column("tracking_links", "sub1")
    op.drop_column("tracking_links", "sub2")
    op.drop_column("tracking_links", "sub3")


def downgrade() -> None:
    op.add_column("tracking_links", sa.Column("source", sa.String(100), nullable=True))
    op.add_column("tracking_links", sa.Column("sub1", sa.String(255), nullable=True))
    op.add_column("tracking_links", sa.Column("sub2", sa.String(255), nullable=True))
    op.add_column("tracking_links", sa.Column("sub3", sa.String(255), nullable=True))
    op.execute("UPDATE tracking_links SET status = 'active' WHERE status = 'ACTIVE'")
    op.execute("UPDATE tracking_links SET status = 'disabled' WHERE status = 'DISABLED'")
    op.alter_column(
        "tracking_links",
        "status",
        existing_type=sa.String(20),
        server_default="active",
        existing_nullable=True,
    )
