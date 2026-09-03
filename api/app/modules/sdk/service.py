from datetime import datetime, timezone

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sdk.dto import SdkCredentialCreated, SdkCredentialStatus
from app.modules.sdk.repository import SdkScriptRepository
from app.modules.sdk.script_id import is_valid_script_id


class SdkCredentialService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SdkScriptRepository(db)

    async def get_status(self, business_id: int) -> SdkCredentialStatus:
        from app.modules.sites.repository import SiteRepository

        scripts = await self.repository.list_by_business(business_id)
        sites = await SiteRepository(self.db).list_by_business(business_id)
        if not scripts and not sites:
            return SdkCredentialStatus(
                configured=False,
                integration_status="not_configured",
                sites_count=0,
                connected_sites=0,
            )
        connected = [script for script in scripts if script.last_success_at]
        last_success = max((script.last_success_at for script in connected), default=None)
        primary = sites[0] if sites else None
        primary_script = scripts[0] if scripts else None
        return SdkCredentialStatus(
            configured=True,
            script_id=(primary.site_key if primary else None) or (primary_script.script_id if primary_script else None),
            created_at=(primary.created_at if primary else None) or (primary_script.created_at if primary_script else None),
            last_success_at=last_success,
            integration_status="connected" if connected else "awaiting_first_request",
            sites_count=len(sites),
            connected_sites=len(connected),
        )

    async def create(self, business_id: int, user_id: str | int) -> SdkCredentialCreated:
        from app.modules.sites.service import SiteService

        site = await SiteService(self.db).create_from_business_website(business_id, user_id)
        return SdkCredentialCreated(script_id=site.site_key, created_at=site.created_at or datetime.now(timezone.utc))

    async def ingest(self, raw: str) -> None:
        payload = _parse_json(raw)
        if payload is None:
            return
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            script_id = str(
                item.get("script_id") or item.get("site_id") or item.get("site_key") or ""
            ).strip().lower()
            if not is_valid_script_id(script_id):
                continue
            script = await self.repository.get_by_script_id(script_id)
            if not script:
                continue
            was_connected = script.last_success_at is not None
            await self.repository.mark_success(script_id)
            if not was_connected:
                from app.modules.notifications.service import NotificationService, site_domain

                _, domain = await site_domain(self.db, script.site_id)
                await NotificationService(self.db).notify_sdk_connected(
                    business_id=script.business_id,
                    site_id=script.site_id,
                    domain=domain,
                )


def _parse_json(raw: str):
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
