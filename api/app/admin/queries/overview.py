from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import iso
from app.common.enums import LinkStatus, OfferStatus, SiteStatus
from app.core.config import settings
from app.modules.businesses.models import Business
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.postback.attempt import PostbackAttempt, PostbackAttemptResult
from app.modules.postback.models import PostbackCredential
from app.modules.sdk.models import SdkScript
from app.modules.sites.models import Site


def _health(last_at: datetime | None, *, configured: bool | None = None) -> dict:
    now = datetime.now(timezone.utc)
    if configured is False:
        return {"status": "no_activity", "label": "Не настроено", "last_at": iso(last_at)}
    if last_at is None:
        return {"status": "no_activity", "label": "Нет активности", "last_at": None}
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    age = now - last_at
    if age <= timedelta(hours=24):
        return {"status": "healthy", "label": "В норме", "last_at": iso(last_at)}
    if age <= timedelta(days=7):
        return {"status": "degraded", "label": "Деградация", "last_at": iso(last_at)}
    return {"status": "no_activity", "label": "Нет активности", "last_at": iso(last_at)}


async def overview(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    businesses = (await db.execute(select(func.count(Business.id)))).scalar_one()
    partners = (await db.execute(select(func.count(PartnerProfile.id)))).scalar_one()
    connected_sites = (
        await db.execute(
            select(func.count(Site.id))
            .select_from(Site)
            .join(SdkScript, SdkScript.site_id == Site.id)
            .where(SdkScript.last_success_at.is_not(None), Site.status == SiteStatus.ACTIVE.value)
        )
    ).scalar_one()
    active_offers = (
        await db.execute(select(func.count(Offer.id)).where(Offer.status == OfferStatus.ACTIVE.value))
    ).scalar_one()
    active_links = (
        await db.execute(
            select(func.count(TrackingLink.id)).where(TrackingLink.status == LinkStatus.ACTIVE.value)
        )
    ).scalar_one()

    clicks_24h = (
        await db.execute(select(func.count(Click.id)).where(Click.created_at >= day_ago))
    ).scalar_one()
    conversions_24h = (
        await db.execute(select(func.count(Conversion.id)).where(Conversion.created_at >= day_ago))
    ).scalar_one()
    accepted_24h = (
        await db.execute(
            select(func.count(PostbackAttempt.id)).where(
                PostbackAttempt.received_at >= day_ago,
                PostbackAttempt.result == PostbackAttemptResult.ACCEPTED,
            )
        )
    ).scalar_one()
    rejected_24h = (
        await db.execute(
            select(func.count(PostbackAttempt.id)).where(
                PostbackAttempt.received_at >= day_ago,
                PostbackAttempt.result == PostbackAttemptResult.REJECTED,
            )
        )
    ).scalar_one()

    last_click = (await db.execute(select(func.max(Click.created_at)))).scalar_one()
    last_sdk = (await db.execute(select(func.max(SdkScript.last_success_at)))).scalar_one()
    last_postback = (await db.execute(select(func.max(PostbackAttempt.received_at)))).scalar_one()
    if last_postback is None:
        last_postback = (await db.execute(select(func.max(PostbackCredential.last_success_at)))).scalar_one()

    return {
        "counts": {
            "businesses": businesses,
            "connected_sites": connected_sites,
            "partners": partners,
            "active_offers": active_offers,
            "active_tracking_links": active_links,
        },
        "activity_24h": {
            "clicks": clicks_24h,
            "conversions": conversions_24h,
            "accepted_postbacks": accepted_24h,
            "rejected_postbacks": rejected_24h,
        },
        "health": {
            "tracking_redirects": _health(last_click),
            "clickstream_receiving": _health(last_sdk),
            "postback_receiving": _health(last_postback),
            "email_sending": _health(
                None,
                configured=settings.postbox_enabled,
            )
            if not settings.postbox_enabled
            else {"status": "healthy", "label": "В норме", "last_at": None},
        },
    }
