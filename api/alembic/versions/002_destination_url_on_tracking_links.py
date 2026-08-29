"""Move destination URL from Offer to TrackingLink.

Revision ID: 002
Revises: 001
Create Date: 2026-08-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracking_links", sa.Column("destination_url", sa.String(500), nullable=True))

    op.execute(
        """
        UPDATE tracking_links AS tl
        SET destination_url = COALESCE(
            tl.destination_url_override,
            o.destination_url
        )
        FROM offers AS o
        WHERE o.id = tl.offer_id
        """
    )
    op.execute(
        """
        UPDATE tracking_links
        SET destination_url = 'https://example.com'
        WHERE destination_url IS NULL OR destination_url = ''
        """
    )

    op.alter_column(
        "tracking_links",
        "destination_url",
        existing_type=sa.String(500),
        nullable=False,
    )
    op.drop_column("tracking_links", "destination_url_override")
    op.drop_column("offers", "destination_url")


def downgrade() -> None:
    op.add_column("offers", sa.Column("destination_url", sa.String(500), nullable=True))
    op.add_column(
        "tracking_links",
        sa.Column("destination_url_override", sa.String(500), nullable=True),
    )
    op.execute(
        """
        UPDATE tracking_links
        SET destination_url_override = destination_url
        """
    )
    op.drop_column("tracking_links", "destination_url")
