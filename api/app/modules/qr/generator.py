from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_H

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
QR_VERSION = 6
BOX_SIZE = 12
BORDER = 4
# Keep the logo small relative to the QR so high-level error correction can recover the center.
LOGO_MAX_RATIO = 0.18
LOGO_PAD_RATIO = 0.035


@lru_cache(maxsize=1)
def _load_logo() -> Image.Image:
    if not LOGO_PATH.is_file():
        raise FileNotFoundError(f"RefIQ logo asset is missing: {LOGO_PATH}")
    logo = Image.open(LOGO_PATH).convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    return logo


class QrCodeGenerator:
    """Turn a public TrackingLink URL into PNG bytes with a centered RefIQ logo."""

    def generate(self, url: str) -> bytes:
        qr = qrcode.QRCode(
            version=QR_VERSION,
            error_correction=ERROR_CORRECT_H,
            box_size=BOX_SIZE,
            border=BORDER,
        )
        qr.add_data(url)
        qr.make(fit=False)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        image = self._overlay_logo(image)
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _overlay_logo(self, qr_image: Image.Image) -> Image.Image:
        logo = _load_logo()
        qr_size = qr_image.size[0]
        max_logo = max(24, int(qr_size * LOGO_MAX_RATIO))
        logo = logo.copy()
        logo.thumbnail((max_logo, max_logo), Image.Resampling.LANCZOS)

        pad = max(6, int(qr_size * LOGO_PAD_RATIO))
        plate_size = (logo.width + pad * 2, logo.height + pad * 2)
        radius = max(8, pad)
        plate = Image.new("RGBA", plate_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(plate)
        draw.rounded_rectangle(
            (0, 0, plate_size[0] - 1, plate_size[1] - 1),
            radius=radius,
            fill=(255, 255, 255, 255),
        )
        plate.paste(logo, (pad, pad), logo)

        canvas = qr_image.convert("RGBA")
        x = (canvas.width - plate.width) // 2
        y = (canvas.height - plate.height) // 2
        canvas.paste(plate, (x, y), plate)
        return canvas.convert("RGB")
