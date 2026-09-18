"""Legal entity verification: source, attempts, admin actor.

Revision ID: 029
Revises: 028
Create Date: 2026-09-18

Existing LegalEntity rows keep their current verification_status.
Nothing is auto-promoted to VERIFIED.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("legal_entities", sa.Column("verification_source", sa.String(32), nullable=True))
    op.add_column("legal_entities", sa.Column("verification_reason_code", sa.String(64), nullable=True))
    op.add_column("legal_entities", sa.Column("verified_by_admin_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_legal_entities_verification_source", "legal_entities", ["verification_source"])
    op.create_index("ix_legal_entities_verified_by_admin_id", "legal_entities", ["verified_by_admin_id"])
    op.create_foreign_key(
        "fk_legal_entities_verified_by_admin_id",
        "legal_entities",
        "admin_users",
        ["verified_by_admin_id"],
        ["id"],
    )
    op.create_table(
        "legal_entity_verification_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("legal_entity_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("actor_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("public_reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_request_id", sa.String(128), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["legal_entity_id"], ["legal_entities.id"]),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_legal_entity_verification_attempts_legal_entity_id",
        "legal_entity_verification_attempts",
        ["legal_entity_id"],
    )
    op.create_index(
        "ix_legal_entity_verification_attempts_provider",
        "legal_entity_verification_attempts",
        ["provider"],
    )
    op.create_index(
        "ix_legal_entity_verification_attempts_status",
        "legal_entity_verification_attempts",
        ["status"],
    )
    op.create_index(
        "ix_legal_entity_verification_attempts_actor_admin_id",
        "legal_entity_verification_attempts",
        ["actor_admin_id"],
    )
    op.create_index(
        "ix_legal_entity_verification_attempts_actor_user_id",
        "legal_entity_verification_attempts",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_table("legal_entity_verification_attempts")
    op.drop_constraint("fk_legal_entities_verified_by_admin_id", "legal_entities", type_="foreignkey")
    op.drop_index("ix_legal_entities_verified_by_admin_id", table_name="legal_entities")
    op.drop_index("ix_legal_entities_verification_source", table_name="legal_entities")
    op.drop_column("legal_entities", "verified_by_admin_id")
    op.drop_column("legal_entities", "verification_reason_code")
    op.drop_column("legal_entities", "verification_source")
