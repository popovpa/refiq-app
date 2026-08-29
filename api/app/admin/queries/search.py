"""Exact-identifier-first global search. No Elasticsearch."""

from __future__ import annotations

import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.queries.common import iso
from app.core.ids import parse_id
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.sites.models import Site
from app.modules.users.models import User

RQCID_RE = re.compile(r"^[a-z0-9]{12}$")
SHORT_RE = re.compile(r"^[a-z0-9]{7}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ID_RE = re.compile(r"^\d+$")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search(db: AsyncSession, q: str, *, limit: int = 20) -> dict:
    query = (q or "").strip()
    if not query:
        return {"query": query, "items": []}

    items: list[dict] = []
    lowered = query.lower()

    if RQCID_RE.fullmatch(lowered):
        items.extend(await _rqcid(db, lowered))
    if SHORT_RE.fullmatch(lowered):
        items.extend(await _short_code(db, lowered))
    if EMAIL_RE.fullmatch(lowered):
        items.extend(await _email(db, lowered))
    if ID_RE.fullmatch(query):
        items.extend(await _ids(db, parse_id(query)))
    if "." in lowered and " " not in lowered and not lowered.startswith("http"):
        items.extend(await _domain(db, lowered))

    if len(items) < limit:
        items.extend(await _names(db, query, limit=limit))

    seen: set[tuple[str, str]] = set()
    unique = []
    for item in items:
        key = (item["type"], str(item["id"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return {"query": query, "items": unique}


async def _rqcid(db: AsyncSession, rqcid: str) -> list[dict]:
    click = (await db.execute(select(Click).where(Click.rqcid == rqcid))).scalar_one_or_none()
    conversion = (
        await db.execute(select(Conversion).where(Conversion.click_id == rqcid))
    ).scalar_one_or_none()
    items = []
    if click:
        items.append(
            {
                "type": "click",
                "id": click.id,
                "title": rqcid,
                "subtitle": "Click",
                "href": f"/trace/{rqcid}",
                "primary_action": "open_trace",
                "rqcid": rqcid,
            }
        )
    if conversion:
        items.append(
            {
                "type": "conversion",
                "id": conversion.id,
                "title": f"Conversion #{conversion.id}",
                "subtitle": rqcid,
                "href": f"/conversions/{conversion.id}",
                "primary_action": "open_trace",
                "rqcid": rqcid,
            }
        )
    if click or conversion:
        items.insert(
            0,
            {
                "type": "trace",
                "id": rqcid,
                "title": rqcid,
                "subtitle": "rqcid trace",
                "href": f"/trace/{rqcid}",
                "primary_action": "open_trace",
                "rqcid": rqcid,
            },
        )
    return items


async def _short_code(db: AsyncSession, code: str) -> list[dict]:
    row = (
        await db.execute(
            select(TrackingLink, Offer, Business, PartnerProfile)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .join(Business, Business.id == Offer.business_id)
            .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
            .where(TrackingLink.short_code == code)
        )
    ).first()
    if not row:
        return []
    link, offer, business, partner = row
    return [
        {
            "type": "tracking_link",
            "id": link.id,
            "title": link.short_code,
            "subtitle": f"Offer: {offer.name}",
            "href": f"/tracking-links/{link.id}",
            "context": {
                "offer": offer.name,
                "business": business.name,
                "partner": partner.display_name,
                "status": link.status,
            },
        }
    ]


async def _email(db: AsyncSession, email: str) -> list[dict]:
    items = []
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    if user:
        membership = (
            await db.execute(
                select(BusinessMembership, Business)
                .join(Business, Business.id == BusinessMembership.business_id)
                .where(
                    BusinessMembership.user_id == user.id,
                    BusinessMembership.permission_role == "owner",
                )
            )
        ).first()
        if membership:
            _, business = membership
            items.append(
                {
                    "type": "business",
                    "id": business.id,
                    "title": business.name,
                    "subtitle": user.email,
                    "href": f"/businesses/{business.id}",
                }
            )
        partner = (
            await db.execute(select(PartnerProfile).where(PartnerProfile.user_id == user.id))
        ).scalar_one_or_none()
        if partner:
            items.append(
                {
                    "type": "partner",
                    "id": partner.id,
                    "title": partner.display_name or user.email,
                    "subtitle": user.email,
                    "href": f"/partners/{partner.id}",
                }
            )
    return items


async def _ids(db: AsyncSession, entity_id: int) -> list[dict]:
    items = []
    business = await db.get(Business, entity_id)
    if business:
        items.append({"type": "business", "id": business.id, "title": business.name, "href": f"/businesses/{business.id}"})
    partner = await db.get(PartnerProfile, entity_id)
    if partner:
        items.append(
            {
                "type": "partner",
                "id": partner.id,
                "title": partner.display_name or f"Partner #{partner.id}",
                "href": f"/partners/{partner.id}",
            }
        )
    offer = await db.get(Offer, entity_id)
    if offer:
        items.append({"type": "offer", "id": offer.id, "title": offer.name, "href": f"/offers/{offer.id}"})
    conversion = await db.get(Conversion, entity_id)
    if conversion:
        items.append(
            {
                "type": "conversion",
                "id": conversion.id,
                "title": f"Conversion #{conversion.id}",
                "href": f"/conversions/{conversion.id}",
                "rqcid": conversion.click_id,
                "primary_action": "open_trace" if conversion.click_id else None,
            }
        )
    link = await db.get(TrackingLink, entity_id)
    if link:
        items.append(
            {
                "type": "tracking_link",
                "id": link.id,
                "title": link.short_code,
                "href": f"/tracking-links/{link.id}",
            }
        )
    return items


async def _domain(db: AsyncSession, domain: str) -> list[dict]:
    site = (await db.execute(select(Site).where(func.lower(Site.domain) == domain))).scalar_one_or_none()
    if not site:
        return []
    business = await db.get(Business, site.business_id)
    return [
        {
            "type": "site",
            "id": site.id,
            "title": site.domain,
            "subtitle": business.name if business else None,
            "href": f"/sites/{site.id}",
        }
    ]


async def _names(db: AsyncSession, query: str, *, limit: int) -> list[dict]:
    pattern = f"%{_escape_like(query.lower())}%"
    items = []
    businesses = (
        await db.execute(
            select(Business).where(func.lower(Business.name).like(pattern)).limit(limit)
        )
    ).scalars().all()
    for business in businesses:
        items.append({"type": "business", "id": business.id, "title": business.name, "href": f"/businesses/{business.id}"})
    offers = (
        await db.execute(select(Offer).where(func.lower(Offer.name).like(pattern)).limit(limit))
    ).scalars().all()
    for offer in offers:
        items.append({"type": "offer", "id": offer.id, "title": offer.name, "href": f"/offers/{offer.id}"})
    partners = (
        await db.execute(
            select(PartnerProfile).where(func.lower(PartnerProfile.display_name).like(pattern)).limit(limit)
        )
    ).scalars().all()
    for partner in partners:
        items.append(
            {
                "type": "partner",
                "id": partner.id,
                "title": partner.display_name,
                "href": f"/partners/{partner.id}",
            }
        )
    conversions = (
        await db.execute(
            select(Conversion).where(func.lower(Conversion.external_id).like(pattern)).limit(5)
        )
    ).scalars().all()
    for conversion in conversions:
        items.append(
            {
                "type": "conversion",
                "id": conversion.id,
                "title": conversion.external_id,
                "subtitle": "Order / external ID",
                "href": f"/conversions/{conversion.id}",
            }
        )
    return items
