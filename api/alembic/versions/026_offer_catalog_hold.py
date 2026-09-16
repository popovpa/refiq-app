"""Offer category catalog, hold period, and conversion snapshot.

Revision ID: 026
Revises: 025
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.modules.catalog.data import CATEGORIES, LEGACY_CATEGORY_MAP, VERTICALS
from app.modules.catalog.traffic import LEGACY_TRAFFIC_MAP, normalize_traffic_source

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offer_verticals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name_ru", sa.String(160), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "offer_categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vertical_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name_ru", sa.String(160), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["vertical_id"], ["offer_verticals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_offer_categories_code"),
    )
    op.create_index("ix_offer_categories_code", "offer_categories", ["code"])
    op.create_index("ix_offer_categories_vertical_id", "offer_categories", ["vertical_id"])

    op.add_column("offers", sa.Column("category_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_offers_category_id", "offers", "offer_categories", ["category_id"], ["id"])
    op.create_index("ix_offers_category_id", "offers", ["category_id"])
    op.add_column("offers", sa.Column("hold_period_days", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("conversions", sa.Column("hold_period_days_snapshot", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("conversions", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("commissions", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    vertical_ids: dict[str, int] = {}
    for index, (code, name_ru, name_en) in enumerate(VERTICALS):
        result = bind.execute(
            sa.text(
                "INSERT INTO offer_verticals (code, name_ru, name_en, sort_order, is_active) "
                "VALUES (:code, :name_ru, :name_en, :sort_order, true) RETURNING id"
            ),
            {"code": code, "name_ru": name_ru, "name_en": name_en, "sort_order": index},
        )
        vertical_ids[code] = result.scalar_one()

    category_ids: dict[str, int] = {}
    for index, (vertical_code, code, name_ru, name_en) in enumerate(CATEGORIES):
        result = bind.execute(
            sa.text(
                "INSERT INTO offer_categories (vertical_id, code, name_ru, name_en, sort_order, is_active) "
                "VALUES (:vertical_id, :code, :name_ru, :name_en, :sort_order, true) RETURNING id"
            ),
            {
                "vertical_id": vertical_ids[vertical_code],
                "code": code,
                "name_ru": name_ru,
                "name_en": name_en,
                "sort_order": index,
            },
        )
        category_ids[code] = result.scalar_one()

    offers = bind.execute(sa.text("SELECT id, category, geo, allowed_traffic FROM offers")).mappings().all()
    for offer in offers:
        raw_category = offer["category"]
        mapped = LEGACY_CATEGORY_MAP.get(raw_category or "") or raw_category
        category_id = category_ids.get(mapped) if mapped else None
        if category_id is None and mapped:
            category_id = category_ids.get("OTHER")
            mapped = "OTHER" if category_id else mapped
        traffic = offer["allowed_traffic"] or []
        if isinstance(traffic, str):
            import json

            traffic = json.loads(traffic)
        normalized = []
        seen = set()
        for item in traffic:
            code = normalize_traffic_source(item) or LEGACY_TRAFFIC_MAP.get(str(item))
            if code and code not in seen:
                seen.add(code)
                normalized.append(code)
        geo = offer["geo"] or ""
        geo_codes = [part.strip().upper() for part in geo.replace(";", ",").split(",") if part.strip()]
        geo_codes = [code for code in geo_codes if len(code) == 2 and code.isalpha()]
        bind.execute(
            sa.text(
                "UPDATE offers SET category = :category, category_id = :category_id, "
                "geo = :geo, allowed_traffic = CAST(:traffic AS JSON) WHERE id = :id"
            ),
            {
                "id": offer["id"],
                "category": mapped,
                "category_id": category_id,
                "geo": ",".join(geo_codes),
                "traffic": __import__("json").dumps(normalized),
            },
        )


def downgrade() -> None:
    op.drop_column("commissions", "available_at")
    op.drop_column("conversions", "available_at")
    op.drop_column("conversions", "hold_period_days_snapshot")
    op.drop_constraint("fk_offers_category_id", "offers", type_="foreignkey")
    op.drop_index("ix_offers_category_id", table_name="offers")
    op.drop_column("offers", "hold_period_days")
    op.drop_column("offers", "category_id")
    op.drop_index("ix_offer_categories_vertical_id", table_name="offer_categories")
    op.drop_index("ix_offer_categories_code", table_name="offer_categories")
    op.drop_table("offer_categories")
    op.drop_table("offer_verticals")
