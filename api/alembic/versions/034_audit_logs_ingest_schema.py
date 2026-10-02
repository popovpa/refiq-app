"""Replace legacy audit_logs with Kafka ingest schema for data-ingestor.

Revision ID: 034
Revises: 033
Create Date: 2026-10-03

Legacy rows are preserved in audit_logs_legacy. The new audit_logs table
matches data-ingestor append-only contract (event_id UNIQUE, JSONB blocks).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("audit_logs", "audit_logs_legacy")

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("changed_fields", JSONB, nullable=True),
        sa.Column("before_data", JSONB, nullable=True),
        sa.Column("after_data", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_audit_logs_event_id"),
    )
    op.create_index(
        "audit_logs_occurred_at_idx",
        "audit_logs",
        ["occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )
    op.create_index(
        "audit_logs_entity_idx",
        "audit_logs",
        ["entity_type", "entity_id", "occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )
    op.create_index(
        "audit_logs_account_idx",
        "audit_logs",
        ["account_id", "occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )
    op.create_index(
        "audit_logs_actor_idx",
        "audit_logs",
        ["actor_id", "occurred_at"],
        unique=False,
        postgresql_ops={"occurred_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("audit_logs_actor_idx", table_name="audit_logs")
    op.drop_index("audit_logs_account_idx", table_name="audit_logs")
    op.drop_index("audit_logs_entity_idx", table_name="audit_logs")
    op.drop_index("audit_logs_occurred_at_idx", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.rename_table("audit_logs_legacy", "audit_logs")
