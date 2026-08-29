"""Allow deleting creatives linked from promo generation items.

Revision ID: 023
Revises: 022
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "offer_promo_generation_items_promo_material_id_fkey",
        "offer_promo_generation_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "offer_promo_generation_items_promo_material_id_fkey",
        "offer_promo_generation_items",
        "creatives",
        ["promo_material_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "offer_promo_generation_items_promo_material_id_fkey",
        "offer_promo_generation_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "offer_promo_generation_items_promo_material_id_fkey",
        "offer_promo_generation_items",
        "creatives",
        ["promo_material_id"],
        ["id"],
    )
