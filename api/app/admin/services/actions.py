from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.audit.service import record_admin_action
from app.admin.auth.models import AdminUser
from app.common.enums import BusinessStatus, LinkStatus, OfferStatus, PartnerStatus, SiteStatus
from app.core.exceptions import AppError, NotFoundError
from app.modules.businesses.models import Business
from app.modules.links.models import TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.qr.service import QrCodeService
from app.modules.sites.service import SiteService


class AdminActionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _require_reason(self, reason: str) -> str:
        value = (reason or "").strip()
        if not value:
            raise AppError("REASON_REQUIRED", "Reason is required", 422)
        return value

    async def suspend_business(self, admin: AdminUser, business_id: int, reason: str) -> Business:
        reason = await self._require_reason(reason)
        business = await self.db.get(Business, business_id)
        if not business:
            raise NotFoundError("Business")
        business.status = BusinessStatus.SUSPENDED.value
        business.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="SUSPEND_BUSINESS",
            entity_type="business",
            entity_id=business.id,
            reason=reason,
        )
        return business

    async def activate_business(self, admin: AdminUser, business_id: int, reason: str) -> Business:
        reason = await self._require_reason(reason)
        business = await self.db.get(Business, business_id)
        if not business:
            raise NotFoundError("Business")
        business.status = BusinessStatus.ACTIVE.value
        business.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="ACTIVATE_BUSINESS",
            entity_type="business",
            entity_id=business.id,
            reason=reason,
        )
        return business

    async def block_partner(self, admin: AdminUser, partner_id: int, reason: str) -> PartnerProfile:
        reason = await self._require_reason(reason)
        partner = await self.db.get(PartnerProfile, partner_id)
        if not partner:
            raise NotFoundError("Partner")
        partner.status = PartnerStatus.SUSPENDED.value
        partner.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="BLOCK_PARTNER",
            entity_type="partner",
            entity_id=partner.id,
            reason=reason,
        )
        return partner

    async def unblock_partner(self, admin: AdminUser, partner_id: int, reason: str) -> PartnerProfile:
        reason = await self._require_reason(reason)
        partner = await self.db.get(PartnerProfile, partner_id)
        if not partner:
            raise NotFoundError("Partner")
        partner.status = PartnerStatus.ACTIVE.value
        partner.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="UNBLOCK_PARTNER",
            entity_type="partner",
            entity_id=partner.id,
            reason=reason,
        )
        return partner

    async def deactivate_site(self, admin: AdminUser, site_id: int, reason: str):
        reason = await self._require_reason(reason)
        from app.modules.sites.models import Site

        site = await self.db.get(Site, site_id)
        if not site:
            raise NotFoundError("Site")
        result = await SiteService(self.db).disable(site.business_id, site.id, admin.id)
        await record_admin_action(
            self.db,
            admin=admin,
            action="DEACTIVATE_SITE",
            entity_type="site",
            entity_id=site.id,
            reason=reason,
            details={"domain": site.domain},
        )
        return result

    async def activate_site(self, admin: AdminUser, site_id: int, reason: str):
        reason = await self._require_reason(reason)
        from app.modules.sites.models import Site

        site = await self.db.get(Site, site_id)
        if not site:
            raise NotFoundError("Site")
        result = await SiteService(self.db).enable(site.business_id, site.id, admin.id)
        await record_admin_action(
            self.db,
            admin=admin,
            action="ACTIVATE_SITE",
            entity_type="site",
            entity_id=site.id,
            reason=reason,
            details={"domain": site.domain},
        )
        return result

    async def pause_offer(self, admin: AdminUser, offer_id: int, reason: str) -> Offer:
        reason = await self._require_reason(reason)
        offer = await self.db.get(Offer, offer_id)
        if not offer:
            raise NotFoundError("Offer")
        offer.status = OfferStatus.PAUSED.value
        offer.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="PAUSE_OFFER",
            entity_type="offer",
            entity_id=offer.id,
            reason=reason,
        )
        return offer

    async def activate_offer(self, admin: AdminUser, offer_id: int, reason: str) -> Offer:
        reason = await self._require_reason(reason)
        offer = await self.db.get(Offer, offer_id)
        if not offer:
            raise NotFoundError("Offer")
        offer.status = OfferStatus.ACTIVE.value
        offer.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="ACTIVATE_OFFER",
            entity_type="offer",
            entity_id=offer.id,
            reason=reason,
        )
        return offer

    async def pause_link(self, admin: AdminUser, link_id: int, reason: str) -> TrackingLink:
        reason = await self._require_reason(reason)
        link = await self.db.get(TrackingLink, link_id)
        if not link:
            raise NotFoundError("TrackingLink")
        link.status = LinkStatus.DISABLED.value
        link.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="PAUSE_TRACKING_LINK",
            entity_type="tracking_link",
            entity_id=link.id,
            reason=reason,
        )
        return link

    async def activate_link(self, admin: AdminUser, link_id: int, reason: str) -> TrackingLink:
        reason = await self._require_reason(reason)
        link = await self.db.get(TrackingLink, link_id)
        if not link:
            raise NotFoundError("TrackingLink")
        from app.modules.offers.models import Offer

        offer = await self.db.get(Offer, link.offer_id)
        if offer and offer.status != OfferStatus.ACTIVE.value:
            raise AppError(
                "OFFER_INACTIVE",
                "Tracking link cannot be activated because the offer is inactive.",
                409,
            )
        link.status = LinkStatus.ACTIVE.value
        link.updated_at = datetime.now(timezone.utc)
        await record_admin_action(
            self.db,
            admin=admin,
            action="ACTIVATE_TRACKING_LINK",
            entity_type="tracking_link",
            entity_id=link.id,
            reason=reason,
        )
        return link

    async def regenerate_qr(self, admin: AdminUser, link_id: int, reason: str) -> TrackingLink:
        reason = await self._require_reason(reason)
        link = await self.db.get(TrackingLink, link_id)
        if not link:
            raise NotFoundError("TrackingLink")
        await QrCodeService().create_quietly(link.short_code)
        await record_admin_action(
            self.db,
            admin=admin,
            action="REGENERATE_QR",
            entity_type="tracking_link",
            entity_id=link.id,
            reason=reason,
            details={"short_code": link.short_code},
        )
        return link
