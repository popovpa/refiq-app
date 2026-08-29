from __future__ import annotations

import structlog
from fastapi.responses import Response

from app.modules.assets.service import get_asset_storage
from app.modules.assets.storage import AssetStorage
from app.modules.links.short_code import is_valid_short_code
from app.modules.qr.generator import QrCodeGenerator

logger = structlog.get_logger()

TRACKING_LINK_BASE_URL = "https://go.refiq.ru"
QR_OBJECT_PREFIX = "qr-codes"
PNG_CONTENT_TYPE = "image/png"


def tracking_link_url(short_code: str) -> str:
    return f"{TRACKING_LINK_BASE_URL}/{short_code}"


def qr_object_key(short_code: str) -> str:
    if not is_valid_short_code(short_code):
        raise ValueError("Invalid tracking link short code")
    return f"{QR_OBJECT_PREFIX}/{short_code}.png"


def png_response(data: bytes, *, as_attachment: bool = False, short_code: str | None = None) -> Response:
    if as_attachment:
        filename = f"{short_code or 'qr-code'}.png"
        disposition = f'attachment; filename="{filename}"'
    else:
        disposition = "inline"
    return Response(
        content=data,
        media_type=PNG_CONTENT_TYPE,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=3600",
        },
    )


class QrCodeService:
    def __init__(
        self,
        storage: AssetStorage | None = None,
        generator: QrCodeGenerator | None = None,
    ):
        self.storage = storage or get_asset_storage()
        self.generator = generator or QrCodeGenerator()

    async def create_quietly(self, short_code: str) -> None:
        """Best-effort QR create after TrackingLink save. Never raises."""
        try:
            png = self.generator.generate(tracking_link_url(short_code))
            await self.storage.put(qr_object_key(short_code), png, PNG_CONTENT_TYPE)
        except Exception:
            logger.exception("qr_code_create_failed", short_code=short_code)

    async def get_or_create(self, short_code: str) -> bytes:
        key = qr_object_key(short_code)
        if await self.storage.exists(key):
            return await self.storage.get(key)
        png = self.generator.generate(tracking_link_url(short_code))
        try:
            await self.storage.put(key, png, PNG_CONTENT_TYPE)
        except Exception:
            logger.exception("qr_code_self_heal_upload_failed", short_code=short_code)
        return png
