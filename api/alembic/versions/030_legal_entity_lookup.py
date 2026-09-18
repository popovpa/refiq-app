"""Legal entity lookup metadata for registry prefill.

Revision ID: 030
Revises: 029
Create Date: 2026-09-19

Existing LegalEntity rows stay unchanged. New columns are nullable.
Lookup metadata is not a verification decision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("legal_entities", sa.Column("kpp", sa.String(9), nullable=True))
    op.add_column("legal_entities", sa.Column("lookup_provider", sa.String(32), nullable=True))
    op.add_column("legal_entities", sa.Column("lookup_provider_reference", sa.String(128), nullable=True))
    op.add_column("legal_entities", sa.Column("lookup_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("legal_entities", sa.Column("registry_status", sa.String(32), nullable=True))
    op.add_column(
        "legal_entities",
        sa.Column("lookup_invalid", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("legal_entities", sa.Column("lookup_metadata", JSONB, nullable=True))
    op.create_index("ix_legal_entities_lookup_provider", "legal_entities", ["lookup_provider"])


def downgrade() -> None:
    op.drop_index("ix_legal_entities_lookup_provider", table_name="legal_entities")
    op.drop_column("legal_entities", "lookup_metadata")
    op.drop_column("legal_entities", "lookup_invalid")
    op.drop_column("legal_entities", "registry_status")
    op.drop_column("legal_entities", "lookup_at")
    op.drop_column("legal_entities", "lookup_provider_reference")
    op.drop_column("legal_entities", "lookup_provider")
    op.drop_column("legal_entities", "kpp")
