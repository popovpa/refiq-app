from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import SiteStatus
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import parse_id
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer
from app.modules.sdk.models import SdkScript
from app.modules.sdk.repository import SdkScriptRepository
from app.modules.sdk.script_id import generate_script_id
from app.modules.sites.domain import hostname_from_url, normalize_site_input
from app.modules.sites.dto import SiteResponse
from app.modules.sites.models import Site
from app.modules.sites.repository import SiteRepository
from app.modules.system.audit import write_audit_log
from app.modules.system.models import BusinessSettings


class SiteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SiteRepository(db)
        self.scripts = SdkScriptRepository(db)

    async def list_sites(self, business_id: int) -> list[SiteResponse]:
        sites = await self.repository.list_by_business(business_id)
        return [await self._to_response(site) for site in sites]

    async def get_site(self, business_id: int, site_id: int) -> SiteResponse:
        site = await self._owned(business_id, site_id)
        return await self._to_response(site)

    async def create(
        self,
        business_id: int,
        user_id: str | int,
        *,
        url: str,
        name: str | None = None,
        site_key: str | None = None,
    ) -> SiteResponse:
        domain, suggested = normalize_site_input(url)
        existing = await self.repository.get_by_business_domain(business_id, domain)
        if existing:
            raise ConflictError("Сайт с таким адресом уже добавлен")

        now = datetime.now(timezone.utc)
        key = site_key or await self._unique_site_key()
        label = (name or "").strip() or suggested
        site = Site(
            business_id=business_id,
            name=label,
            domain=domain,
            status=SiteStatus.ACTIVE.value,
            site_key=key,
            created_at=now,
            updated_at=now,
        )
        await self.repository.add(site)
        await self.scripts.add(
            SdkScript(
                business_id=business_id,
                site_id=site.id,
                script_id=key,
                created_by_user_id=parse_id(user_id),
                created_at=now,
            )
        )
        await write_audit_log(
            self.db,
            user_id=parse_id(user_id),
            action="site.created",
            resource_type="site",
            resource_id=str(site.id),
            details={"domain": domain, "site_key": key},
        )
        return await self._to_response(site)

    async def create_from_business_website(self, business_id: int, user_id: str | int) -> SiteResponse:
        existing_scripts = await self.scripts.list_by_business(business_id)
        if existing_scripts:
            raise AppError(code="CONFLICT", message="SCRIPT_ID already exists", status_code=409)
        website = await self._business_website(business_id)
        if not website:
            raise AppError("SITE_URL_REQUIRED", "Добавьте сайт, чтобы подключить web tracking", 400)
        return await self.create(business_id, user_id, url=website)

    async def update_name(self, business_id: int, site_id: int, name: str) -> SiteResponse:
        site = await self._owned(business_id, site_id)
        label = name.strip()
        if not label:
            raise AppError("INVALID_SITE_NAME", "Укажите название сайта", 400)
        site.name = label
        site.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return await self._to_response(site)

    async def disable(self, business_id: int, site_id: int, user_id: str | int) -> SiteResponse:
        site = await self._owned(business_id, site_id)
        if site.status != SiteStatus.DISABLED.value:
            now = datetime.now(timezone.utc)
            site.status = SiteStatus.DISABLED.value
            site.disabled_at = now
            site.updated_at = now
            await write_audit_log(
                self.db,
                user_id=parse_id(user_id),
                action="site.disabled",
                resource_type="site",
                resource_id=str(site.id),
                details={"domain": site.domain},
            )
        return await self._to_response(site)

    async def enable(self, business_id: int, site_id: int, user_id: str | int) -> SiteResponse:
        site = await self._owned(business_id, site_id)
        if site.status != SiteStatus.ACTIVE.value:
            now = datetime.now(timezone.utc)
            site.status = SiteStatus.ACTIVE.value
            site.disabled_at = None
            site.updated_at = now
            await write_audit_log(
                self.db,
                user_id=parse_id(user_id),
                action="site.enabled",
                resource_type="site",
                resource_id=str(site.id),
                details={"domain": site.domain},
            )
        return await self._to_response(site)

    async def delete(self, business_id: int, site_id: int, user_id: str | int) -> None:
        site = await self._owned(business_id, site_id)
        if await self._is_used(site):
            raise AppError(
                "SITE_IN_USE",
                "Сайт уже используется. Его можно только отключить.",
                409,
            )
        script = await self.scripts.get_by_site_id(site.id)
        if script:
            await self.db.delete(script)
            await self.db.flush()
        await write_audit_log(
            self.db,
            user_id=parse_id(user_id),
            action="site.deleted",
            resource_type="site",
            resource_id=str(site.id),
            details={"domain": site.domain, "site_key": site.site_key},
        )
        await self.repository.delete(site)

    async def match_destination(self, business_id: int, url: str | None) -> dict:
        hostname = hostname_from_url(url)
        if not hostname:
            return {"site_id": None, "site_name": None, "site_domain": None, "site_missing": False}
        site = await self.repository.get_by_business_domain(business_id, hostname)
        if site:
            return {
                "site_id": site.id,
                "site_name": site.name,
                "site_domain": site.domain,
                "site_missing": False,
            }
        return {
            "site_id": None,
            "site_name": None,
            "site_domain": hostname,
            "site_missing": True,
        }

    async def _owned(self, business_id: int, site_id: int) -> Site:
        site = await self.repository.get_owned(business_id, site_id)
        if not site:
            raise NotFoundError("Site")
        return site

    async def _to_response(self, site: Site) -> SiteResponse:
        script = await self.scripts.get_by_site_id(site.id)
        last_success = script.last_success_at if script else None
        if site.status == SiteStatus.DISABLED.value:
            display_status = "disabled"
        elif last_success:
            display_status = "connected"
        else:
            display_status = "needs_setup"
        return SiteResponse(
            id=site.id,
            business_id=site.business_id,
            name=site.name,
            domain=site.domain,
            status=site.status,
            display_status=display_status,
            site_key=site.site_key,
            sdk_status="connected" if last_success else "not_detected",
            last_success_at=last_success,
            created_at=site.created_at,
            updated_at=site.updated_at,
            disabled_at=site.disabled_at,
            can_delete=not await self._is_used(site),
        )

    async def _is_used(self, site: Site) -> bool:
        script = await self.scripts.get_by_site_id(site.id)
        if script and script.last_success_at is not None:
            return True
        offer_ids = list(
            (await self.db.execute(select(Offer.id).where(Offer.business_id == site.business_id))).scalars()
        )
        if not offer_ids:
            return False
        links = list(
            (
                await self.db.execute(select(TrackingLink).where(TrackingLink.offer_id.in_(offer_ids)))
            ).scalars()
        )
        return any(hostname_from_url(link.destination_url) == site.domain for link in links)

    async def _unique_site_key(self) -> str:
        for _ in range(16):
            candidate = generate_script_id()
            if not await self.repository.exists_site_key(candidate) and not await self.scripts.exists_script_id(
                candidate
            ):
                return candidate
        raise RuntimeError("Failed to generate a unique site_key")

    async def _business_website(self, business_id: int) -> str | None:
        row = (
            await self.db.execute(select(BusinessSettings).where(BusinessSettings.business_id == business_id))
        ).scalar_one_or_none()
        website = (row.settings or {}).get("website") if row else None
        if isinstance(website, str) and website.strip():
            return website.strip()
        return None
