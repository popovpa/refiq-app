from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.postback.validator import RQCID_PATTERN

PARTNER_RQCID_COOKIE = "refiq_prqcid"
PARTNER_RQCID_MAX_AGE = 90 * 24 * 3600


@dataclass
class AttributionResult:
    tracking_link_id: int
    partner_id: int | None
    partner_tracking_link_id: int | None


def within_attribution_window(click: Click, offer: Offer, *, now: datetime | None = None) -> bool:
    created = click.created_at
    if created is None:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    window = offer.attribution_window_days or 30
    return (now or datetime.now(timezone.utc)) <= created + timedelta(days=window)


def cookie_partner_rqcid(raw: str | None) -> str | None:
    value = (raw or "").strip().lower()
    if RQCID_PATTERN.fullmatch(value):
        return value
    return None


async def resolve_conversion_attribution(
    db: AsyncSession,
    *,
    click: Click,
    link: TrackingLink,
    offer: Offer,
) -> AttributionResult:
    if link.partner_id is not None:
        return AttributionResult(
            tracking_link_id=link.id,
            partner_id=link.partner_id,
            partner_tracking_link_id=link.id,
        )

    partner_click = await _eligible_partner_click(db, click=click, offer=offer)
    if not partner_click:
        return AttributionResult(
            tracking_link_id=link.id,
            partner_id=None,
            partner_tracking_link_id=None,
        )
    partner_link = (
        await db.execute(select(TrackingLink).where(TrackingLink.id == partner_click.tracking_link_id))
    ).scalar_one_or_none()
    if (
        not partner_link
        or partner_link.partner_id is None
        or partner_link.offer_id != offer.id
    ):
        return AttributionResult(
            tracking_link_id=link.id,
            partner_id=None,
            partner_tracking_link_id=None,
        )
    return AttributionResult(
        tracking_link_id=link.id,
        partner_id=partner_link.partner_id,
        partner_tracking_link_id=partner_link.id,
    )


async def _eligible_partner_click(
    db: AsyncSession,
    *,
    click: Click,
    offer: Offer,
) -> Click | None:
    if click.partner_rqcid:
        stored = (
            await db.execute(
                select(Click)
                .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
                .where(
                    Click.rqcid == click.partner_rqcid,
                    TrackingLink.partner_id.is_not(None),
                    TrackingLink.offer_id == offer.id,
                    Click.id != click.id,
                )
            )
        ).scalar_one_or_none()
        if stored and within_attribution_window(stored, offer):
            return stored

    filters = [
        Click.id != click.id,
        Click.created_at <= (click.created_at or datetime.now(timezone.utc)),
        TrackingLink.offer_id == offer.id,
        TrackingLink.partner_id.is_not(None),
    ]
    if click.client_ip and click.user_agent:
        filters.extend([Click.client_ip == click.client_ip, Click.user_agent == click.user_agent])
    elif click.client_ip:
        filters.append(Click.client_ip == click.client_ip)
    else:
        return None

    window_start = None
    created = click.created_at
    if created is not None:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        window_start = created - timedelta(days=offer.attribution_window_days or 30)
        filters.append(Click.created_at >= window_start)

    return (
        await db.execute(
            select(Click)
            .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
            .where(*filters)
            .order_by(Click.created_at.desc(), Click.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
