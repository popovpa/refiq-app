"""Normalize tracking link short codes to 7-char [a-z0-9].

Revision ID: 003
Revises: 002
Create Date: 2026-08-16

"""
from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
LENGTH = 7


def _generate(used: set[str]) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if code not in used:
            used.add(code)
            return code


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM tracking_links")).fetchall()

    for index, row in enumerate(rows):
        conn.execute(
            sa.text("UPDATE tracking_links SET short_code = :code WHERE id = :id"),
            {"code": f"!{index:06d}", "id": row.id},
        )

    used: set[str] = set()
    for row in rows:
        new_code = _generate(used)
        conn.execute(
            sa.text("UPDATE tracking_links SET short_code = :code WHERE id = :id"),
            {"code": new_code, "id": row.id},
        )

    op.alter_column(
        "tracking_links",
        "short_code",
        existing_type=sa.String(20),
        type_=sa.String(7),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "tracking_links",
        "short_code",
        existing_type=sa.String(7),
        type_=sa.String(20),
        existing_nullable=False,
    )
