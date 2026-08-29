import struct
import zlib

import httpx
import pytest

from app.modules.ai.website.extract import extract_page
from app.modules.ai.website.images import sniff_image
from app.modules.ai.website.provider import WebsiteContextProvider
from app.modules.ai.website.ssrf import UnsafeUrlError, parse_public_url


def make_png(width: int, height: int, color: tuple[int, int, int] = (40, 120, 180)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


async def public_host(host: str) -> None:
    from app.modules.ai.website.ssrf import _as_ip, ensure_public_ip

    ip = _as_ip(host)
    if ip is not None:
        ensure_public_ip(ip)
        return
    if host in {"public.test", "cdn.test"}:
        return
    raise UnsafeUrlError("hostname")


def provider_for(handler) -> WebsiteContextProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    return WebsiteContextProvider(client=client, resolve_host=public_host)


def test_ssrf_blocks_localhost():
    with pytest.raises(UnsafeUrlError):
        parse_public_url("http://localhost/admin")


def test_ssrf_blocks_loopback_ip():
    with pytest.raises(UnsafeUrlError):
        parse_public_url("http://127.0.0.1/secret")


def test_ssrf_blocks_private_ip():
    with pytest.raises(UnsafeUrlError):
        parse_public_url("http://192.168.10.4/x")


def test_ssrf_blocks_metadata():
    with pytest.raises(UnsafeUrlError):
        parse_public_url("http://169.254.169.254/latest/meta-data")


def test_ssrf_blocks_docker_hostname():
    with pytest.raises(UnsafeUrlError):
        parse_public_url("http://host.docker.internal/api")


def test_extract_prefers_og_and_skips_icons():
    html = """
    <html><head>
      <title>CRM Pro</title>
      <meta name="description" content="Облачная CRM">
      <meta property="og:image" content="https://cdn.test/og.png">
      <script type="application/ld+json">
        {"@type":"Product","name":"CRM Pro","image":"https://cdn.test/product.png","offers":{"price":"9900","priceCurrency":"RUB"}}
      </script>
    </head>
    <body>
      <h1>CRM для продаж</h1>
      <img src="/favicon.ico" class="icon" width="16" height="16" alt="favicon">
      <p>Облачная CRM помогает команде закрывать сделки быстрее и прозрачнее.</p>
      <a href="/buy">Купить</a>
    </body></html>
    """
    extract = extract_page(html, "https://public.test/crm")
    assert extract.title == "CRM Pro"
    assert extract.og_image == "https://cdn.test/og.png"
    assert extract.product_images == ["https://cdn.test/product.png"]
    assert extract.h1 == "CRM для продаж"
    assert any("9900" in item for item in extract.price_hints)
    assert "Купить" in extract.ctas
    assert not any("favicon" in (item or "") for item in extract.hero_images)


def test_tiny_png_is_rejected():
    tiny = make_png(1, 1)
    assert sniff_image(tiny, "image/png") is None
    large = make_png(200, 200)
    sniffed = sniff_image(large, "image/png")
    assert sniffed is not None
    assert sniffed[0] == "png"
    assert sniffed[1] == 200


@pytest.mark.asyncio
async def test_fetch_uses_og_image():
    image = make_png(240, 240)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crm":
            html = """
            <html><head>
              <title>CRM</title>
              <meta property="og:image" content="https://cdn.test/og.png">
            </head>
            <body><h1>CRM</h1><p>Облачная система для отдела продаж и партнёров.</p></body></html>
            """
            return httpx.Response(200, headers={"content-type": "text/html"}, content=html.encode())
        if request.url.path == "/og.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=image)
        return httpx.Response(404)

    provider = provider_for(handler)
    context = await provider.fetch("https://public.test/crm")
    assert context.status == "ok"
    assert context.title == "CRM"
    assert context.image_source == "og:image"
    assert context.image_data_url and context.image_data_url.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_fetch_uses_product_image_when_og_missing():
    image = make_png(180, 180)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crm":
            html = """
            <html><head>
              <script type="application/ld+json">
                {"@type":"Product","name":"CRM Pro","image":"https://cdn.test/product.png"}
              </script>
            </head><body><h1>CRM Pro</h1><p>Продукт для партнёрских продаж в B2B.</p></body></html>
            """
            return httpx.Response(200, headers={"content-type": "text/html"}, content=html.encode())
        if request.url.path == "/product.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=image)
        return httpx.Response(404)

    context = await provider_for(handler).fetch("https://public.test/crm")
    assert context.status == "ok"
    assert context.image_source == "schema.org/Product.image"


@pytest.mark.asyncio
async def test_fetch_skips_tiny_icon_image():
    tiny = make_png(16, 16)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/crm":
            html = """
            <html><head><title>CRM</title></head>
            <body>
              <h1>CRM</h1>
              <img src="https://cdn.test/favicon.png" class="logo" width="16" height="16">
              <p>Облачная CRM для партнёрской программы и продаж.</p>
            </body></html>
            """
            return httpx.Response(200, headers={"content-type": "text/html"}, content=html.encode())
        if request.url.path == "/favicon.png":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=tiny)
        return httpx.Response(404)

    context = await provider_for(handler).fetch("https://public.test/crm")
    assert context.status == "ok"
    assert context.image_data_url is None


@pytest.mark.asyncio
async def test_unavailable_page_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"down")

    context = await provider_for(handler).fetch("https://public.test/crm")
    assert context.status == "unavailable"
    assert context.reason == "http_error"


@pytest.mark.asyncio
async def test_unsupported_content_type_is_skipped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    context = await provider_for(handler).fetch("https://public.test/file.pdf")
    assert context.status == "unavailable"
    assert context.reason == "unsupported"


@pytest.mark.asyncio
async def test_html_response_is_truncated():
    from app.modules.ai.website import http as website_http

    huge = b"<html><body>" + ("<p>Partner program product text. " * 80_000).encode() + b"</body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=huge)

    original = website_http.MAX_HTML_BYTES
    website_http.MAX_HTML_BYTES = 8_000
    try:
        context = await provider_for(handler).fetch("https://public.test/crm")
    finally:
        website_http.MAX_HTML_BYTES = original
    assert context.status == "ok"
    assert context.content_bytes <= 8_000


@pytest.mark.asyncio
async def test_public_redirect_is_followed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/go":
            return httpx.Response(302, headers={"location": "https://public.test/final"})
        html = "<html><head><title>Final</title></head><body><h1>Final</h1><p>Описание продукта для партнёров после редиректа.</p></body></html>"
        return httpx.Response(200, headers={"content-type": "text/html"}, content=html.encode())

    context = await provider_for(handler).fetch("https://public.test/go")
    assert context.status == "ok"
    assert context.title == "Final"


@pytest.mark.asyncio
async def test_redirect_to_private_network_is_blocked():
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/go":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=b"nope")

    context = await provider_for(handler).fetch("https://public.test/go")
    assert context.status == "unavailable"
    assert context.reason == "blocked"
    assert all("127.0.0.1" not in item for item in requested)


@pytest.mark.asyncio
async def test_localhost_url_is_blocked_without_request():
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=b"nope")

    context = await provider_for(handler).fetch("http://127.0.0.1/secret")
    assert context.status == "unavailable"
    assert requested == []
