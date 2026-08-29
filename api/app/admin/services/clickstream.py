"""Clickstream / behavioral events provider.

ClickHouse is not wired in this codebase. Keep the Trace API stable and return
no fabricated events until a real store is connected.
"""

from __future__ import annotations


class ClickstreamProvider:
    available = False

    async def events_for_rqcid(self, rqcid: str) -> list[dict]:
        return []


_provider = ClickstreamProvider()


def get_clickstream_provider() -> ClickstreamProvider:
    return _provider
