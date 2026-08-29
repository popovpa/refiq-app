from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "template", "nav", "footer"}
CTA_WORDS = (
    "купить",
    "заказать",
    "зарегистрир",
    "попробовать",
    "оставить заявку",
    "начать",
    "оформить",
    "buy",
    "get started",
    "sign up",
    "try",
    "pricing",
    "order",
    "subscribe",
)
PRICE_RE = re.compile(
    r"(?:(?:от|from)\s*)?(?:\d[\d\s]{1,8}(?:[.,]\d{1,2})?\s*(?:₽|руб(?:\.|лей)?|\$|usd|eur|€|₽))|"
    r"(?:\$|€)\s*\d[\d\s]{1,8}(?:[.,]\d{1,2})?",
    re.IGNORECASE,
)
BOILERPLATE = (
    "cookie",
    "cookies",
    "согласие на обработку",
    "privacy policy",
    "политик",
    "все права защищены",
    "subscribe to our newsletter",
)

MAX_TEXT = 6000
MAX_HEADINGS = 8
MAX_CTAS = 8
MAX_PRICES = 5


class PageExtract:
    def __init__(self) -> None:
        self.title: str | None = None
        self.meta_description: str | None = None
        self.og_title: str | None = None
        self.og_description: str | None = None
        self.og_image: str | None = None
        self.twitter_image: str | None = None
        self.h1: str | None = None
        self.h2: list[str] = []
        self.texts: list[str] = []
        self.ctas: list[str] = []
        self.product_images: list[str] = []
        self.hero_images: list[str] = []
        self.logo_images: list[str] = []
        self.product_name: str | None = None
        self.product_description: str | None = None
        self.product_type: str | None = None
        self.price_hints: list[str] = []


class _Parser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.extract = PageExtract()
        self._skip = 0
        self._capture: str | None = None
        self._buf: list[str] = []
        self._ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): (value or "").strip() for key, value in attrs}
        if tag in SKIP_TAGS:
            self._skip += 1
            if tag == "script" and "ld+json" in data.get("type", "").lower():
                self._ld = True
                self._capture = "ld"
                self._buf = []
            return
        if self._skip:
            return
        if tag == "title":
            self._capture = "title"
            self._buf = []
        elif tag in {"h1", "h2"}:
            self._capture = tag
            self._buf = []
        elif tag in {"a", "button"}:
            self._capture = "cta"
            self._buf = []
        elif tag == "meta":
            self._meta(data)
        elif tag == "img":
            self._image(data)
        elif tag == "link" and data.get("rel", "").lower() == "image_src":
            href = self._abs(data.get("href"))
            if href:
                self.extract.hero_images.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            if self._ld and tag == "script":
                self._json_ld("".join(self._buf))
                self._ld = False
                self._capture = None
                self._buf = []
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if self._capture in {"title", "h1", "h2", "cta"} and tag in {self._capture, "a", "button"}:
            text = _clean("".join(self._buf))
            if self._capture == "title":
                self.extract.title = self.extract.title or text
            elif self._capture == "h1":
                self.extract.h1 = self.extract.h1 or text
            elif self._capture == "h2" and text:
                self.extract.h2.append(text)
            elif self._capture == "cta" and _is_cta(text):
                self.extract.ctas.append(text)
            self._capture = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._skip and not self._ld:
            return
        if self._capture:
            self._buf.append(data)
            return
        if self._skip:
            return
        text = _clean(data)
        if text and not _boilerplate(text):
            self.extract.texts.append(text)

    def _meta(self, data: dict[str, str]) -> None:
        name = (data.get("name") or data.get("property") or "").lower()
        content = data.get("content") or ""
        if not content:
            return
        if name in {"description"}:
            self.extract.meta_description = self.extract.meta_description or content
        elif name in {"og:title"}:
            self.extract.og_title = content
        elif name in {"og:description"}:
            self.extract.og_description = content
        elif name in {"og:image", "og:image:url", "og:image:secure_url"}:
            url = self._abs(content)
            if url and not self.extract.og_image:
                self.extract.og_image = url
        elif name in {"twitter:image", "twitter:image:src"}:
            url = self._abs(content)
            if url:
                self.extract.twitter_image = url

    def _image(self, data: dict[str, str]) -> None:
        src = self._abs(data.get("src") or _first_srcset(data.get("srcset")))
        if not src:
            return
        blob = " ".join([src, data.get("alt", ""), data.get("class", ""), data.get("id", "")]).lower()
        width = _int(data.get("width"))
        height = _int(data.get("height"))
        if _tiny(width, height) or _tracking(blob):
            return
        if _icon(blob) or _social(blob):
            if _logo(blob):
                self.extract.logo_images.append(src)
            return
        if _logo(blob):
            self.extract.logo_images.append(src)
            return
        if _hero(blob) or (width and width >= 200) or (height and height >= 200):
            self.extract.hero_images.append(src)
        else:
            self.extract.hero_images.append(src)

    def _json_ld(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return
        try:
            payload = json.loads(text)
        except ValueError:
            return
        for item in _ld_items(payload):
            types = item.get("@type")
            labels = types if isinstance(types, list) else [types]
            labels = [str(value).lower() for value in labels if value]
            if "product" not in labels:
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                self.extract.product_name = self.extract.product_name or name.strip()
            description = item.get("description")
            if isinstance(description, str) and description.strip():
                self.extract.product_description = self.extract.product_description or description.strip()
            category = item.get("category")
            if isinstance(category, str) and category.strip():
                self.extract.product_type = self.extract.product_type or category.strip()
            for image in _ld_images(item.get("image")):
                url = self._abs(image)
                if url:
                    self.extract.product_images.append(url)
            offers = item.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency") or ""
                if price not in (None, ""):
                    self.extract.price_hints.append(f"{price} {currency}".strip())

    def _abs(self, value: str | None) -> str | None:
        if not value:
            return None
        return urljoin(self.base_url, value.strip())


def extract_page(html: str, base_url: str) -> PageExtract:
    parser = _Parser(base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    extract = parser.extract
    extract.h2 = _unique(extract.h2)[:MAX_HEADINGS]
    extract.ctas = _unique(extract.ctas)[:MAX_CTAS]
    extract.product_images = _unique(extract.product_images)
    extract.hero_images = _unique(extract.hero_images)
    extract.logo_images = _unique(extract.logo_images)
    prices = list(extract.price_hints)
    for text in extract.texts:
        prices.extend(match.group(0) for match in PRICE_RE.finditer(text))
    extract.price_hints = _unique(prices)[:MAX_PRICES]
    extract.texts = _dedupe_text(extract.texts)
    return extract


def readable_text(extract: PageExtract) -> str:
    parts = []
    for item in extract.texts:
        if item not in parts:
            parts.append(item)
    text = "\n".join(parts)
    return text[:MAX_TEXT].strip()


def _ld_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        items: list[dict] = []
        for item in payload:
            items.extend(_ld_items(item))
        return items
    if not isinstance(payload, dict):
        return []
    if "@graph" in payload:
        return _ld_items(payload["@graph"])
    return [payload]


def _ld_images(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_ld_images(item))
        return result
    if isinstance(value, dict):
        url = value.get("url") or value.get("contentUrl")
        return [url] if isinstance(url, str) else []
    return []


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        result.append(value)
    return result


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if len(item) < 24 or _boilerplate(item):
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in BOILERPLATE)


def _is_cta(text: str) -> bool:
    if not text or len(text) > 48:
        return False
    lowered = text.lower()
    return any(word in lowered for word in CTA_WORDS)


def _int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(re.sub(r"[^\d]", "", value) or "0") or None
    except ValueError:
        return None


def _tiny(width: int | None, height: int | None) -> bool:
    if width is not None and width <= 2:
        return True
    if height is not None and height <= 2:
        return True
    if width is not None and height is not None and width < 32 and height < 32:
        return True
    return False


def _tracking(blob: str) -> bool:
    return any(token in blob for token in ("pixel", "tracker", "1x1", "spacer", "beacon", "analytics"))


def _icon(blob: str) -> bool:
    return any(token in blob for token in ("favicon", "icon", "sprite", "ui-", "button"))


def _social(blob: str) -> bool:
    return any(token in blob for token in ("facebook", "twitter", "vk.com", "telegram", "share", "social"))


def _logo(blob: str) -> bool:
    return "logo" in blob


def _hero(blob: str) -> bool:
    return any(token in blob for token in ("hero", "product", "cover", "og-image", "main-image"))


def _first_srcset(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(",")[0].strip().split(" ")[0]
