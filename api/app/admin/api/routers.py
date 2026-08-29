from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.permissions import AdminPermission, require_permission
from app.admin.queries import catalog, overview as overview_q, search as search_q, traffic, trace as trace_q
from app.admin.schemas import ActionReason
from app.admin.services.actions import AdminActionService
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.ids import parse_id
from app.modules.qr.service import QrCodeService, png_response

read = require_permission(AdminPermission.READ.value)
ops = require_permission(AdminPermission.OPERATIONS.value)
finance = require_permission(AdminPermission.FINANCE.value)

overview_router = APIRouter()
search_router = APIRouter()
resources_router = APIRouter()
actions_router = APIRouter()
trace_router = APIRouter()
audit_router = APIRouter()


@overview_router.get("/overview")
async def get_overview(_admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await overview_q.overview(db)


@search_router.get("/search")
async def global_search(q: str = Query("", max_length=200), _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await search_q.search(db, q)


@trace_router.get("/trace/{rqcid}")
async def get_trace(rqcid: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await trace_q.build_trace(db, rqcid.strip().lower())


@resources_router.get("/businesses")
async def list_businesses(
    q: str | None = None,
    status: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    has_connected_sites: bool | None = None,
    has_active_offers: bool | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_businesses(
        db,
        q=q,
        status=status,
        created_from=created_from,
        created_to=created_to,
        has_connected_sites=has_connected_sites,
        has_active_offers=has_active_offers,
        page=page,
        per_page=per_page,
    )


@resources_router.get("/businesses/lookup")
async def lookup_businesses(
    search: str | None = Query(default=None, max_length=200),
    id: int | None = Query(default=None),
    limit: int = Query(20, ge=1, le=50),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.lookup_businesses(db, search=search, business_id=id, limit=limit)


@resources_router.get("/businesses/{business_id}")
async def get_business(business_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await catalog.get_business(db, parse_id(business_id))


@resources_router.get("/partners")
async def list_partners(
    q: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_partners(db, q=q, status=status, page=page, per_page=per_page)


@resources_router.get("/partners/{partner_id}")
async def get_partner(partner_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await catalog.get_partner(db, parse_id(partner_id))


@resources_router.get("/sites")
async def list_sites(
    business_id: int | None = None,
    status: str | None = None,
    sdk: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_sites(
        db, business_id=business_id, status=status, sdk=sdk, page=page, per_page=per_page
    )


@resources_router.get("/sites/{site_id}")
async def get_site(site_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await catalog.get_site(db, parse_id(site_id))


@resources_router.get("/offers")
async def list_offers(
    business_id: int | None = None,
    partner_id: int | None = None,
    status: str | None = None,
    commission_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_offers(
        db,
        business_id=business_id,
        partner_id=partner_id,
        status=status,
        commission_type=commission_type,
        created_from=created_from,
        created_to=created_to,
        page=page,
        per_page=per_page,
    )


@resources_router.get("/offers/{offer_id}")
async def get_offer(offer_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await catalog.get_offer(db, parse_id(offer_id))


@resources_router.get("/tracking-links")
async def list_links(
    q: str | None = None,
    status: str | None = None,
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await catalog.list_tracking_links(
        db,
        q=q,
        status=status,
        business_id=business_id,
        partner_id=partner_id,
        offer_id=offer_id,
        page=page,
        per_page=per_page,
    )


@resources_router.get("/tracking-links/{link_id}")
async def get_link(link_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await catalog.get_tracking_link(db, parse_id(link_id))


@resources_router.get("/tracking-links/{link_id}/qr")
async def get_link_qr(link_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    data = await catalog.get_tracking_link(db, parse_id(link_id))
    png = await QrCodeService().get_or_create(data["short_code"])
    return png_response(png, short_code=data["short_code"])


@resources_router.get("/clicks")
async def list_clicks(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    rqcid: str | None = None,
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_clicks(
        db,
        cursor=cursor,
        limit=limit,
        rqcid=rqcid,
        business_id=business_id,
        partner_id=partner_id,
        offer_id=offer_id,
    )


@resources_router.get("/clicks/{rqcid}")
async def get_click(rqcid: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await traffic.get_click(db, rqcid.strip().lower())


@resources_router.get("/conversions")
async def list_conversions(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    business_id: int | None = None,
    partner_id: int | None = None,
    offer_id: int | None = None,
    status: str | None = None,
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_conversions(
        db,
        cursor=cursor,
        limit=limit,
        business_id=business_id,
        partner_id=partner_id,
        offer_id=offer_id,
        status=status,
    )


@resources_router.get("/conversions/{conversion_id}")
async def get_conversion(conversion_id: str, _admin=Depends(read), db: AsyncSession = Depends(get_db)):
    return await traffic.get_conversion(db, parse_id(conversion_id))


@resources_router.post("/conversions/{conversion_id}/reprocess")
async def reprocess_conversion(conversion_id: str, _admin=Depends(ops)):
    raise AppError(
        "CONVERSION_REPROCESS_NOT_SUPPORTED",
        "Conversion reprocess is not available: there is no safe domain reprocess operation.",
        409,
    )


@resources_router.get("/postbacks")
async def list_postbacks(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    result: str | None = None,
    business_id: int | None = None,
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_postbacks(
        db, cursor=cursor, limit=limit, result=result, business_id=business_id
    )


@resources_router.get("/commissions")
async def list_commissions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    partner_id: int | None = None,
    business_id: int | None = None,
    _admin=Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_commissions(
        db, page=page, per_page=per_page, status=status, partner_id=partner_id, business_id=business_id
    )


@resources_router.get("/commissions/{commission_id}")
async def get_commission(commission_id: str, _admin=Depends(finance), db: AsyncSession = Depends(get_db)):
    return await traffic.get_commission(db, parse_id(commission_id))


@resources_router.get("/payouts")
async def list_payouts(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    partner_id: int | None = None,
    _admin=Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_payouts(db, page=page, per_page=per_page, status=status, partner_id=partner_id)


@resources_router.get("/payouts/{payout_id}")
async def get_payout(payout_id: str, _admin=Depends(finance), db: AsyncSession = Depends(get_db)):
    return await traffic.get_payout(db, parse_id(payout_id))


@audit_router.get("/audit")
async def list_audit(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    admin_user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    _admin=Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await traffic.list_audit(
        db,
        cursor=cursor,
        limit=limit,
        admin_user_id=admin_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@actions_router.post("/businesses/{business_id}/suspend")
async def suspend_business(
    business_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    business = await AdminActionService(db).suspend_business(admin, parse_id(business_id), payload.reason)
    return {"id": business.id, "status": business.status}


@actions_router.post("/businesses/{business_id}/activate")
async def activate_business(
    business_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    business = await AdminActionService(db).activate_business(admin, parse_id(business_id), payload.reason)
    return {"id": business.id, "status": business.status}


@actions_router.post("/partners/{partner_id}/block")
async def block_partner(
    partner_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    partner = await AdminActionService(db).block_partner(admin, parse_id(partner_id), payload.reason)
    return {"id": partner.id, "status": partner.status}


@actions_router.post("/partners/{partner_id}/unblock")
async def unblock_partner(
    partner_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    partner = await AdminActionService(db).unblock_partner(admin, parse_id(partner_id), payload.reason)
    return {"id": partner.id, "status": partner.status}


@actions_router.post("/sites/{site_id}/deactivate")
async def deactivate_site(
    site_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    site = await AdminActionService(db).deactivate_site(admin, parse_id(site_id), payload.reason)
    return {"id": site.id, "status": site.status}


@actions_router.post("/sites/{site_id}/activate")
async def activate_site(
    site_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    site = await AdminActionService(db).activate_site(admin, parse_id(site_id), payload.reason)
    return {"id": site.id, "status": site.status}


@actions_router.post("/offers/{offer_id}/pause")
async def pause_offer(
    offer_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    offer = await AdminActionService(db).pause_offer(admin, parse_id(offer_id), payload.reason)
    return {"id": offer.id, "status": offer.status}


@actions_router.post("/offers/{offer_id}/activate")
async def activate_offer(
    offer_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    offer = await AdminActionService(db).activate_offer(admin, parse_id(offer_id), payload.reason)
    return {"id": offer.id, "status": offer.status}


@actions_router.post("/tracking-links/{link_id}/pause")
async def pause_link(
    link_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    link = await AdminActionService(db).pause_link(admin, parse_id(link_id), payload.reason)
    return {"id": link.id, "status": link.status}


@actions_router.post("/tracking-links/{link_id}/activate")
async def activate_link(
    link_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    link = await AdminActionService(db).activate_link(admin, parse_id(link_id), payload.reason)
    return {"id": link.id, "status": link.status}


@actions_router.post("/tracking-links/{link_id}/regenerate-qr")
async def regenerate_qr(
    link_id: str,
    payload: ActionReason,
    admin=Depends(ops),
    db: AsyncSession = Depends(get_db),
):
    link = await AdminActionService(db).regenerate_qr(admin, parse_id(link_id), payload.reason)
    return {"id": link.id, "short_code": link.short_code}
