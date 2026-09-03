import secrets

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.links.models import Click, TrackingLink, TrackingLinkStatus
from app.modules.links.short_code import SHORT_CODE_PATTERN
from app.modules.offers.models import Offer
from app.modules.promotion.attribution import (
    PARTNER_RQCID_COOKIE,
    PARTNER_RQCID_MAX_AGE,
    cookie_partner_rqcid,
)

router = APIRouter()

_RQCID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _generate_rqcid() -> str:
    return "".join(secrets.choice(_RQCID_ALPHABET) for _ in range(12))


def _client_ip(request: Request) -> str | None:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:45]
    if request.client and request.client.host:
        return request.client.host[:45]
    return None


@router.get("/go/{short_code}")
async def redirect_tracking_link(
    request: Request,
    short_code: str = Path(pattern=SHORT_CODE_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrackingLink).where(
            TrackingLink.short_code == short_code,
            TrackingLink.status == TrackingLinkStatus.ACTIVE.value,
        )
    )
    link = result.scalar_one_or_none()
    if not link or not link.destination_url:
        raise NotFoundError("Link")

    offer = (await db.execute(select(Offer).where(Offer.id == link.offer_id))).scalar_one_or_none()
    if not offer or offer.status != "active":
        raise NotFoundError("Link")

    rqcid = None
    for _ in range(8):
        candidate = _generate_rqcid()
        exists = await db.scalar(select(Click.id).where(Click.rqcid == candidate))
        if not exists:
            rqcid = candidate
            break
    if not rqcid:
        raise NotFoundError("Link")

    stored_partner_rqcid = None if link.partner_id else cookie_partner_rqcid(
        request.cookies.get(PARTNER_RQCID_COOKIE)
    )
    db.add(
        Click(
            tracking_link_id=link.id,
            rqcid=rqcid,
            partner_rqcid=stored_partner_rqcid,
            client_ip=_client_ip(request),
            user_agent=(request.headers.get("user-agent") or None),
            referer=(request.headers.get("referer") or None),
        )
    )
    await db.flush()

    response = RedirectResponse(url=link.destination_url, status_code=302)
    if link.partner_id:
        response.set_cookie(
            PARTNER_RQCID_COOKIE,
            rqcid,
            max_age=PARTNER_RQCID_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return response
