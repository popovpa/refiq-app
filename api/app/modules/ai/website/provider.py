from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpx
import structlog

from app.modules.ai.website.extract import extract_page, readable_text
from app.modules.ai.website.http import (
    FetchError,
    default_headers,
    default_timeout,
    fetch_public,
    hostname_for_log,
)
from app.modules.ai.website.images import sniff_image, to_data_url
from app.modules.ai.website.models import WebsiteContext
from app.modules.ai.website.ssrf import UnsafeUrlError, ensure_public_host, normalize_product_url

logger = structlog.get_logger()

ResolveHost = Callable[[str], Awaitable[None]]


class WebsiteContextProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        resolve_host: ResolveHost | None = None,
    ):
        self._client = client
        self._resolve_host = resolve_host or ensure_public_host

    async def fetch(self, url: str) -> WebsiteContext:
        started = datetime.now(timezone.utc)
        try:
            normalized = normalize_product_url(url)
        except UnsafeUrlError:
            return WebsiteContext.unavailable(url, "blocked")
        try:
            page = await self._fetch_html(normalized)
            extract = extract_page(_decode_html(page.data, page.content_type), page.url)
            image_url, image_source = _pick_image(extract)
            image_data_url = await self._fetch_image(image_url) if image_url else None
            main_text = readable_text(extract)
            context = WebsiteContext(
                source_url=normalized,
                status="ok",
                title=_first(extract.og_title, extract.title, extract.h1, extract.product_name),
                description=_first(extract.og_description, extract.meta_description, extract.product_description),
                h1=extract.h1,
                headings=extract.h2,
                main_text=main_text,
                product_name=extract.product_name,
                product_description=extract.product_description,
                price_hints=extract.price_hints,
                cta_hints=extract.ctas,
                product_type_hint=extract.product_type,
                image_data_url=image_data_url,
                image_source=image_source if image_data_url else None,
                content_bytes=len(page.data),
                extracted_chars=len(main_text),
            )
            _log(context, started, ok=True)
            return context
        except (UnsafeUrlError, FetchError) as exc:
            reason = "blocked" if isinstance(exc, UnsafeUrlError) else exc.reason
            context = WebsiteContext.unavailable(normalized, reason)
            _log(context, started, ok=False)
            return context
        except Exception:
            logger.warning("website_context_failed", host=hostname_for_log(normalized))
            context = WebsiteContext.unavailable(normalized, "parse_error")
            _log(context, started, ok=False)
            return context

    async def _fetch_html(self, url: str):
        return await self._with_client(
            lambda client: fetch_public(client, url, kind="html", resolve_host=self._resolve_host)
        )

    async def _fetch_image(self, url: str) -> str | None:
        try:
            resource = await self._with_client(
                lambda client: fetch_public(client, url, kind="image", resolve_host=self._resolve_host)
            )
        except (UnsafeUrlError, FetchError):
            return None
        sniffed = sniff_image(resource.data, resource.content_type)
        if not sniffed:
            return None
        kind, _width, _height = sniffed
        return to_data_url(resource.data, kind)

    async def _with_client(self, operation):
        if self._client is not None:
            return await operation(self._client)
        async with httpx.AsyncClient(
            timeout=default_timeout(),
            follow_redirects=False,
            headers=default_headers(),
            trust_env=False,
        ) as client:
            return await operation(client)


_provider = WebsiteContextProvider()


async def load_website_context(url: str) -> WebsiteContext:
    return await _provider.fetch(url)


def _pick_image(extract) -> tuple[str | None, str | None]:
    if extract.og_image:
        return extract.og_image, "og:image"
    if extract.twitter_image:
        return extract.twitter_image, "twitter:image"
    if extract.product_images:
        return extract.product_images[0], "schema.org/Product.image"
    if extract.hero_images:
        return extract.hero_images[0], "hero"
    if extract.logo_images:
        return extract.logo_images[0], "logo"
    return None, None


def _first(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _decode_html(raw: bytes, content_type: str) -> str:
    charset = None
    if "charset=" in content_type.lower():
        charset = content_type.split("charset=", 1)[1].split(";")[0].strip().strip("\"'")
    for encoding in (charset, "utf-8", "cp1251", "latin-1"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _log(context: WebsiteContext, started: datetime, *, ok: bool) -> None:
    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info(
        "website_context_fetch",
        host=hostname_for_log(context.source_url),
        status=context.status,
        reason=context.reason,
        duration_ms=duration_ms,
        content_bytes=context.content_bytes,
        extracted_chars=context.extracted_chars,
        image=bool(context.image_data_url),
        ok=ok,
    )
