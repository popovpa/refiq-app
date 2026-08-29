from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.local import LocalAssetStorage
from app.modules.assets.models import Asset
from app.modules.assets.storage import AssetStorage

_storage: AssetStorage | None = None


def get_asset_storage() -> AssetStorage:
    global _storage
    if _storage is None:
        from app.core.config import settings

        if settings.s3_enabled:
            from app.modules.assets.s3 import S3AssetStorage

            _storage = S3AssetStorage()
        else:
            _storage = LocalAssetStorage()
    return _storage


def set_asset_storage(storage: AssetStorage | None) -> None:
    global _storage
    _storage = storage


class AssetService:
    def __init__(self, db: AsyncSession, storage: AssetStorage | None = None):
        self.db = db
        self.storage = storage or get_asset_storage()

    async def store_image(
        self,
        data: bytes,
        *,
        mime_type: str = "image/png",
        width: int | None = None,
        height: int | None = None,
        extension: str = "png",
        storage_key: str | None = None,
    ) -> Asset:
        key = storage_key or f"{uuid.uuid4().hex}.{extension}"
        await self.storage.put(key, data, mime_type)
        asset = Asset(
            mime_type=mime_type,
            storage_key=key,
            size=len(data),
            width=width,
            height=height,
        )
        self.db.add(asset)
        await self.db.flush()
        return asset

    async def load(self, asset: Asset) -> bytes:
        return await self.storage.get(asset.storage_key)

    async def delete_asset(self, asset: Asset) -> None:
        try:
            await self.storage.delete(asset.storage_key)
        except FileNotFoundError:
            pass
        await self.db.delete(asset)
