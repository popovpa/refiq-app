from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlparse

import httpx

from app.modules.ai.website.ssrf import UnsafeUrlError, ensure_public_host, parse_public_url

USER_AGENT = "RefIQ-OfferContextFetcher/1.0"
MAX_REDIRECTS = 5
MAX_HTML_BYTES = 1_000_000
MAX_IMAGE_BYTES = 2_000_000
HTML_TYPES = {"text/html", "application/xhtml+xml"}
IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0

ResolveHost = Callable[[str], Awaitable[None]]


class FetchError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class FetchedResource:
    def __init__(self, url: str, content_type: str, data: bytes, truncated: bool = False):
        self.url = url
        self.content_type = content_type
        self.data = data
        self.truncated = truncated


def default_timeout() -> httpx.Timeout:
    return httpx.Timeout(CONNECT_TIMEOUT + READ_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)


def default_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }


async def fetch_public(
    client: httpx.AsyncClient,
    url: str,
    *,
    kind: str,
    resolve_host: ResolveHost | None = None,
) -> FetchedResource:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _, host = parse_public_url(current)
        if resolve_host:
            await resolve_host(host)
        else:
            await ensure_public_host(host)
        try:
            async with client.stream("GET", current, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("redirect")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise FetchError("http_error")
                content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                limit = MAX_IMAGE_BYTES if kind == "image" else MAX_HTML_BYTES
                if kind == "html" and content_type and content_type not in HTML_TYPES:
                    raise FetchError("unsupported")
                if (
                    kind == "image"
                    and content_type
                    and content_type not in IMAGE_TYPES
                    and content_type != "application/octet-stream"
                ):
                    raise FetchError("unsupported")
                data, truncated = await _read_limited(response, limit)
                if truncated and kind == "image":
                    raise FetchError("too_large")
                final_url = str(response.url) if response.url else current
                return FetchedResource(final_url, content_type, data, truncated)
        except FetchError:
            raise
        except httpx.TimeoutException as exc:
            raise FetchError("timeout") from exc
        except UnsafeUrlError:
            raise
        except httpx.HTTPError as exc:
            raise FetchError("network") from exc
    raise FetchError("redirect")


async def _read_limited(response: httpx.Response, limit: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    truncated = False
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        if total + len(chunk) > limit:
            chunks.append(chunk[: limit - total])
            truncated = True
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), truncated


def hostname_for_log(url: str) -> str:
    return urlparse(url).hostname or ""
