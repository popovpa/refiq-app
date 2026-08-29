from __future__ import annotations

import struct

MIN_EDGE = 128
MAX_STORED_BYTES = 400_000
ALLOWED_TYPES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}


def sniff_image(data: bytes, content_type: str | None) -> tuple[str, int, int] | None:
    kind = ALLOWED_TYPES.get((content_type or "").split(";")[0].strip().lower())
    header_kind, width, height = _size(data)
    if header_kind is None or width is None or height is None:
        return None
    if kind and kind != header_kind:
        kind = header_kind
    if not kind:
        kind = header_kind
    if min(width, height) < MIN_EDGE:
        return None
    if len(data) > MAX_STORED_BYTES:
        return None
    return kind, width, height


def to_data_url(data: bytes, kind: str) -> str:
    import base64

    mime = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[kind]
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _size(data: bytes) -> tuple[str | None, int | None, int | None]:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg", *_jpeg_size(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", *_webp_size(data)
    return None, None, None


def _jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    while index + 8 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            return width, height
        if marker in {0xD8, 0xD9}:
            index += 2
            continue
        length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        index += 2 + length
    return None, None


def _webp_size(data: bytes) -> tuple[int | None, int | None]:
    kind = data[12:16]
    if kind == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if kind == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if kind == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None, None
