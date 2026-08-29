"""Cursor pagination helpers for event-like admin lists."""

from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import and_, or_


def encode_cursor(created_at: datetime, entity_id: int) -> str:
    raw = f"{created_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        stamp, entity_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(stamp), int(entity_id)
    except (ValueError, UnicodeDecodeError):
        return None


def keyset_before(created_at_col, id_col, cursor: str | None):
    parsed = decode_cursor(cursor)
    if not parsed:
        return True
    created_at, entity_id = parsed
    return or_(
        created_at_col < created_at,
        and_(created_at_col == created_at, id_col < entity_id),
    )


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def as_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)
