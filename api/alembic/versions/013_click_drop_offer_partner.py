"""Drop denormalized offer_id and partner_id from clicks.

Revision ID: 013
Revises: 012
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_columns = {("offer_id",), ("partner_id",)}
    for fk in inspector.get_foreign_keys("clicks"):
        if tuple(fk.get("constrained_columns") or ()) in fk_columns and fk.get("name"):
            op.drop_constraint(fk["name"], "clicks", type_="foreignkey")
    index_columns = {("offer_id",), ("partner_id",)}
    for index in inspector.get_indexes("clicks"):
        if tuple(index.get("column_names") or ()) in index_columns and index.get("name"):
            op.drop_index(index["name"], table_name="clicks")
    op.drop_column("clicks", "offer_id")
    op.drop_column("clicks", "partner_id")


def downgrade() -> None:
    op.add_column("clicks", sa.Column("offer_id", sa.BigInteger(), nullable=True))
    op.add_column("clicks", sa.Column("partner_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("clicks_offer_id_fkey", "clicks", "offers", ["offer_id"], ["id"])
    op.create_foreign_key(
        "clicks_partner_id_fkey", "clicks", "partner_profiles", ["partner_id"], ["id"]
    )
    op.create_index("ix_clicks_offer_id", "clicks", ["offer_id"])
    op.create_index("ix_clicks_partner_id", "clicks", ["partner_id"])
