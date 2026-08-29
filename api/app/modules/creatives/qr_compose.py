from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.modules.creatives.promo_catalog import DEFAULT_QR_LAYOUT
from app.modules.qr.generator import QrCodeGenerator
from app.modules.qr.service import tracking_link_url

_generator = QrCodeGenerator()


def compose_tracking_qr(base_png: bytes, short_code: str, layout: dict | None = None) -> bytes:
    """Overlay a machine-readable TrackingLink QR onto an AI base image. Does not call image AI."""
    payload = layout or {}
    area = payload.get("qr_safe_area") or DEFAULT_QR_LAYOUT["qr_safe_area"]
    base = Image.open(BytesIO(base_png)).convert("RGBA")
    qr = Image.open(BytesIO(_generator.generate(tracking_link_url(short_code)))).convert("RGBA")

    box_w = max(32, int(base.width * float(area.get("w", 0.22))))
    box_h = max(32, int(base.height * float(area.get("h", 0.22))))
    pad = max(6, int(min(box_w, box_h) * 0.08))
    qr.thumbnail((max(24, box_w - pad * 2), max(24, box_h - pad * 2)), Image.Resampling.LANCZOS)

    x = int(base.width * float(area.get("x", 0.74)))
    y = int(base.height * float(area.get("y", 0.74)))
    plate_w = qr.width + pad * 2
    plate_h = qr.height + pad * 2
    x = min(max(0, x), max(0, base.width - plate_w))
    y = min(max(0, y), max(0, base.height - plate_h))

    plate = Image.new("RGBA", (plate_w, plate_h), (255, 255, 255, 240))
    base.paste(plate, (x, y), plate)
    base.paste(qr, (x + pad, y + pad), qr)

    buffer = BytesIO()
    base.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
