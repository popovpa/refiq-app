"""Click destination snapshot and destination URL change audit.

Revision ID: 010
Revises: 009
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clicks", sa.Column("destination_url", sa.String(length=500), nullable=True))
    op.execute(
        """
        UPDATE clicks AS c
        SET destination_url = tl.destination_url
        FROM tracking_links AS tl
        WHERE c.tracking_link_id = tl.id
          AND c.destination_url IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("clicks", "destination_url")
