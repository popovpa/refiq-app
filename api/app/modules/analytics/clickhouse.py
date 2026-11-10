from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class ClickHouseUnavailable(Exception):
    pass


class ClickHouseClient:
    async def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict]:
        database, table = qualified_names()
        sql = sql.replace("FROM clickstream_events", f"FROM {database}.{table}")
        url = settings.CLICKHOUSE_URL.rstrip("/") + "/"
        query_params: dict[str, str] = {
            "database": database,
            "default_format": "JSON",
            "max_execution_time": str(max(1, int(settings.CLICKHOUSE_TIMEOUT_SECONDS))),
            "readonly": "1",
            "wait_end_of_query": "1",
        }
        if settings.CLICKHOUSE_USER:
            query_params["user"] = settings.CLICKHOUSE_USER
        if settings.CLICKHOUSE_PASSWORD:
            query_params["password"] = settings.CLICKHOUSE_PASSWORD
        for key, value in (params or {}).items():
            query_params[f"param_{key}"] = str(value)
        timeout = httpx.Timeout(settings.CLICKHOUSE_TIMEOUT_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, params=query_params, content=sql.encode("utf-8"))
        except httpx.HTTPError as exc:
            raise ClickHouseUnavailable("clickhouse request failed") from exc
        if response.status_code >= 400:
            logger.warning(
                "analytics_clickhouse_query_failed",
                status=response.status_code,
                body=response.text[:300],
            )
            raise ClickHouseUnavailable("clickhouse query failed")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ClickHouseUnavailable("clickhouse response is invalid") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ClickHouseUnavailable("clickhouse response is invalid")
        return data


_client: ClickHouseClient | None = None


def qualified_names() -> tuple[str, str]:
    database = settings.CLICKHOUSE_DATABASE
    table = settings.CLICKHOUSE_TABLE
    if not _IDENT.match(database) or not _IDENT.match(table):
        raise ClickHouseUnavailable("clickhouse identifier is invalid")
    return database, table


def get_clickhouse() -> ClickHouseClient:
    global _client
    if _client is None:
        _client = ClickHouseClient()
    return _client


def set_clickhouse(client: ClickHouseClient | None) -> None:
    global _client
    _client = client
