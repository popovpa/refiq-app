"""Drop destination_url from clicks.

Revision ID: 014
Revises: 013
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("clicks", "destination_url")


def downgrade() -> None:
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
