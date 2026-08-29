from io import BytesIO

import pytest
from PIL import Image

from app.modules.qr.generator import QrCodeGenerator
from app.modules.qr.service import qr_object_key, tracking_link_url

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_qr_object_key_is_derived_from_short_code():
    assert tracking_link_url("abc1234") == "https://go.refiq.ru/abc1234"
    assert qr_object_key("abc1234") == "qr-codes/abc1234.png"
    with pytest.raises(ValueError):
        qr_object_key("../secret")


def test_qr_generator_returns_png_with_centered_logo():
    png = QrCodeGenerator().generate("https://go.refiq.ru/abc1234")
    assert png.startswith(PNG_MAGIC)

    image = Image.open(BytesIO(png)).convert("RGB")
    width, height = image.size
    assert width == height
    assert width >= 256

    cx, cy = width // 2, height // 2
    center = image.crop((cx - 16, cy - 16, cx + 16, cy + 16))
    colors = {center.getpixel((x, y)) for x in range(center.size[0]) for y in range(center.size[1])}
    assert any(pixel[0] != pixel[1] or pixel[1] != pixel[2] for pixel in colors)

    corner = image.getpixel((8, 8))
    assert corner == (255, 255, 255)
