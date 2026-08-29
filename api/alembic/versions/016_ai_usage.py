"""AI usage records for generation telemetry.

Revision ID: 016
Revises: 015
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("generation_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=50), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("cached_input_tokens", sa.Integer, nullable=True),
        sa.Column("reasoning_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("time_to_first_token_ms", sa.Integer, nullable=True),
        sa.Column("provider_request_id", sa.String(length=120), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("actual_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feedback_outcome", sa.String(length=40), nullable=True),
        sa.Column("generated_fields_count", sa.Integer, nullable=True),
        sa.Column("accepted_fields_count", sa.Integer, nullable=True),
        sa.Column("modified_fields_count", sa.Integer, nullable=True),
        sa.Column("rejected_fields_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_usage_generation_id", "ai_usage", ["generation_id"], unique=True)
    op.create_index("ix_ai_usage_provider", "ai_usage", ["provider"])
    op.create_index("ix_ai_usage_model", "ai_usage", ["model"])
    op.create_index("ix_ai_usage_capability", "ai_usage", ["capability"])
    op.create_index("ix_ai_usage_operation", "ai_usage", ["operation"])
    op.create_index("ix_ai_usage_entity_id", "ai_usage", ["entity_id"])
    op.create_index("ix_ai_usage_status", "ai_usage", ["status"])
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_user_id", table_name="ai_usage")
    op.drop_index("ix_ai_usage_status", table_name="ai_usage")
    op.drop_index("ix_ai_usage_entity_id", table_name="ai_usage")
    op.drop_index("ix_ai_usage_operation", table_name="ai_usage")
    op.drop_index("ix_ai_usage_capability", table_name="ai_usage")
    op.drop_index("ix_ai_usage_model", table_name="ai_usage")
    op.drop_index("ix_ai_usage_provider", table_name="ai_usage")
    op.drop_index("ix_ai_usage_generation_id", table_name="ai_usage")
    op.drop_table("ai_usage")
