"""Backfill Site rows from legacy business website + sdk_scripts.

Kept as a Python function so the Alembic revision and tests share the same
deterministic mapping: one Site per existing SCRIPT_ID / website hostname.
"""
from __future__ import annotations

import json
import secrets
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine import Connection

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _hostname(raw: object) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or "." not in hostname:
        return None
    return hostname


def _new_key(used: set[str]) -> str:
    for _ in range(32):
        candidate = "".join(secrets.choice(ALPHABET) for _ in range(5))
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError("Failed to generate a unique site_key")


def backfill_sites(connection: Connection) -> None:
    used_keys = {
        row[0]
        for row in connection.execute(text("SELECT site_key FROM sites")).fetchall()
        if row[0]
    }
    used_keys.update(
        row[0]
        for row in connection.execute(text("SELECT script_id FROM sdk_scripts")).fetchall()
        if row[0]
    )
    existing_pairs = {
        (int(row[0]), row[1])
        for row in connection.execute(text("SELECT business_id, domain FROM sites")).fetchall()
    }

    settings_rows = connection.execute(
        text("SELECT business_id, settings FROM business_settings")
    ).fetchall()
    websites: dict[int, str] = {}
    for business_id, settings in settings_rows:
        payload = settings
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        domain = _hostname(payload.get("website"))
        if domain:
            websites[int(business_id)] = domain

    scripts = connection.execute(
        text(
            """
            SELECT id, business_id, script_id, created_by_user_id, created_at
            FROM sdk_scripts
            WHERE site_id IS NULL
            ORDER BY id
            """
        )
    ).fetchall()

    for script_id_row in scripts:
        script_pk, business_id, script_id, created_by, created_at = script_id_row
        business_id = int(business_id)
        domain = websites.get(business_id) or f"legacy-{script_id}.invalid"
        pair = (business_id, domain)
        if pair in existing_pairs:
            domain = f"legacy-{script_id}.invalid"
            pair = (business_id, domain)
        used_keys.add(script_id)
        connection.execute(
            text(
                """
                INSERT INTO sites (
                    business_id, name, domain, status, site_key, created_at, updated_at
                )
                VALUES (
                    :business_id, :name, :domain, 'active', :site_key, :created_at, :created_at
                )
                """
            ),
            {
                "business_id": business_id,
                "name": domain,
                "domain": domain,
                "site_key": script_id,
                "created_at": created_at,
            },
        )
        site_id = connection.execute(text("SELECT id FROM sites WHERE site_key = :key"), {"key": script_id}).scalar()
        connection.execute(
            text("UPDATE sdk_scripts SET site_id = :site_id WHERE id = :id"),
            {"site_id": site_id, "id": script_pk},
        )
        existing_pairs.add(pair)

    script_businesses = {
        int(row[0])
        for row in connection.execute(text("SELECT DISTINCT business_id FROM sdk_scripts")).fetchall()
    }
    for business_id, domain in websites.items():
        if business_id in script_businesses:
            continue
        pair = (business_id, domain)
        if pair in existing_pairs:
            continue
        key = _new_key(used_keys)
        connection.execute(
            text(
                """
                INSERT INTO sites (
                    business_id, name, domain, status, site_key, created_at, updated_at
                )
                VALUES (
                    :business_id, :name, :domain, 'active', :site_key, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "business_id": business_id,
                "name": domain,
                "domain": domain,
                "site_key": key,
            },
        )
        site_id = connection.execute(text("SELECT id FROM sites WHERE site_key = :key"), {"key": key}).scalar()
        connection.execute(
            text(
                """
                INSERT INTO sdk_scripts (business_id, site_id, script_id, created_at)
                VALUES (:business_id, :site_id, :script_id, CURRENT_TIMESTAMP)
                """
            ),
            {"business_id": business_id, "site_id": site_id, "script_id": key},
        )
        existing_pairs.add(pair)
