"""Drop the pre-ingest audit_logs table preserved as audit_logs_legacy.

Revision ID: 035
Revises: 034
Create Date: 2026-10-03

The admin audit screen reads the ingest table audit_logs. Historical rows
from the old shape are not migrated.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs_legacy")


def downgrade() -> None:
    # The legacy shape is not restored. Recreate an empty compatible table only
    # so a downgrade of 034 can rename it back if that revision is reverted first.
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import JSONB

    op.create_table(
        "audit_logs_legacy",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=50), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
