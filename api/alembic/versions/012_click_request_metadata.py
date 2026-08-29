"""Request metadata on clicks for the tracker redirect path.

Revision ID: 012
Revises: 011
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clicks", sa.Column("client_ip", sa.String(length=45), nullable=True))
    op.add_column("clicks", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("clicks", sa.Column("referer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("clicks", "referer")
    op.drop_column("clicks", "user_agent")
    op.drop_column("clicks", "client_ip")
