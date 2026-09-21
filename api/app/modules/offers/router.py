from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.date_range import resolve_query_range
from app.core.database import get_db
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.conversions.models import Conversion
from app.modules.links.models import TrackingLink
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.modules.catalog.models import OfferCategory
from app.modules.catalog.seed import ensure_catalog
from app.modules.audit.context import audit_context_from_http
from app.modules.offers.audit import record_offer_created, record_offer_mutations, snapshot_offer
from app.modules.offers.models import Offer, OfferCommissionRule, OfferPartnerAccess
from app.modules.offers.service import (
    apply_commission_update,
    ensure_business_partner,
    offer_category_filter,
    offer_link_stats,
    offer_public_fields,
    offer_source_stats,
    offer_stats,
    offer_timeseries,
    partner_access_query,
    serialize_business_partner_access,
)
from app.modules.offers.validation import (
    normalize_partner_notes,
    serialize_geo,
    validate_access_policy,
    validate_allowed_traffic,
    validate_attribution_window_days,
    validate_category_code,
    validate_commission,
    validate_conversion_type,
    validate_geo_codes,
    validate_hold_period_days,
    validate_offer_description,
)
from app.modules.partners.models import PartnerProfile
from app.modules.partners.privacy import partner_public_display_name_from, strip_partner_contact_fields
from app.modules.products.models import Product
from app.modules.users.models import User

router = APIRouter()

VALID_STATUSES = {"draft", "active", "paused", "closing", "archived"}
VALID_ACCESS = {"open", "approval", "invite_only"}


class CreateOfferRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = None
    category: str | None = None
    category_id: int | None = None
    geo: str | list[str] | None = None
    product_name: str | None = None
    product_url: str | None = None
    conversion_type: str = "sale"
    attribution_window_days: int = 30
    hold_period_days: int = 0
    commission_type: str = "percent"
    commission_value: float = 10.0
    commission_currency: str | None = None
    visibility: str = "public"
    access_policy: str = "open"
    allowed_traffic: list[str] | None = None
    forbidden_traffic: list[str] | None = None
    partner_notes: str | None = None
    materials: list[dict] | None = None
    status: str = "draft"


class UpdateOfferRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    category: str | None = None
    category_id: int | None = None
    geo: str | list[str] | None = None
    product_url: str | None = None
    status: str | None = None
    visibility: str | None = None
    access_policy: str | None = None
    conversion_type: str | None = None
    attribution_window_days: int | None = None
    hold_period_days: int | None = None
    commission_type: str | None = None
    commission_value: float | None = None
    commission_currency: str | None = None
    allowed_traffic: list[str] | None = None
    forbidden_traffic: list[str] | None = None
    partner_notes: str | None = None
    materials: list[dict] | None = None


async def _resolve_category(db: AsyncSession, category: str | None, category_id: int | None) -> OfferCategory:
    catalog = await ensure_catalog(db)
    if category_id is not None:
        row = (await db.execute(select(OfferCategory).where(OfferCategory.id == category_id))).scalar_one_or_none()
        if not row or not row.is_active:
            raise AppError("INVALID_CATEGORY", "Выберите категорию", 400)
        return row
    code = validate_category_code(category)
    row = catalog.get(code)
    if not row or not row.is_active:
        raise AppError("INVALID_CATEGORY", "Выберите категорию", 400)
    return row


class InvitePartnerRequest(BaseModel):
    email: str | None = None
    partner_id: int | None = None


class RejectPartnerRequest(BaseModel):
    reason: str


async def _get_business_offer(db: AsyncSession, offer_id: str, business_id: int) -> Offer:
    offer = (
        await db.execute(
            select(Offer).where(Offer.id == parse_id(offer_id), Offer.business_id == business_id)
        )
    ).scalar_one_or_none()
    if not offer:
        raise NotFoundError("Offer")
    return offer


@router.get("")
async def list_offers(
    status: str | None = None,
    access_policy: str | None = None,
    category: str | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    filters = [Offer.business_id == business_id]
    if status:
        filters.append(Offer.status == status)
    if access_policy:
        filters.append(Offer.access_policy == access_policy)
    if category:
        filters.append(offer_category_filter(category))
    if q:
        filters.append(Offer.name.ilike(f"%{q.strip()}%"))

    query = select(Offer).where(*filters).order_by(Offer.created_at.desc())
    total = await db.scalar(select(func.count(Offer.id)).where(*filters))
    offers = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    items = []
    for offer in offers:
        partners_count = await db.scalar(
            select(func.count(OfferPartnerAccess.id)).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.status == "approved",
            )
        )
        stats = await offer_stats(db, offer.id)
        items.append(
            {
                **offer_public_fields(offer),
                "partners_count": partners_count or 0,
                "clicks": stats["clicks"],
                "conversions": stats["conversions"],
                "cr": stats["cr"],
            }
        )

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.post("")
async def create_offer(
    data: CreateOfferRequest,
    request: Request,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    if data.status not in VALID_STATUSES:
        raise ForbiddenError("Invalid offer status")
    access_policy = validate_access_policy(data.access_policy)
    conversion_type = validate_conversion_type(data.conversion_type)
    commission_type, commission_value = validate_commission(data.commission_type, data.commission_value)
    attribution_window_days = validate_attribution_window_days(data.attribution_window_days)
    hold_period_days = validate_hold_period_days(data.hold_period_days)
    category_row = await _resolve_category(db, data.category, data.category_id)
    geo_codes = validate_geo_codes(data.geo)
    allowed_traffic = validate_allowed_traffic(data.allowed_traffic)
    description = validate_offer_description(data.description)
    partner_notes = normalize_partner_notes(data.partner_notes)

    product = Product(
        business_id=business_id,
        name=data.product_name or data.name,
        url=data.product_url,
        description=description,
        status="active",
    )
    db.add(product)
    await db.flush()

    offer = Offer(
        business_id=business_id,
        product_id=product.id,
        name=data.name,
        description=description,
        image_url=data.image_url,
        category=category_row.code,
        category_id=category_row.id,
        geo=serialize_geo(geo_codes),
        hold_period_days=hold_period_days,
        status=data.status,
        visibility=data.visibility,
        access_policy=access_policy,
        conversion_type=conversion_type,
        attribution_window_days=attribution_window_days,
        currency=data.commission_currency or "RUB",
        allowed_traffic=allowed_traffic,
        forbidden_traffic=[],
        partner_notes=partner_notes,
        materials=data.materials or [],
    )
    db.add(offer)
    await db.flush()

    db.add(
        OfferCommissionRule(
            offer_id=offer.id,
            type=commission_type,
            value=commission_value,
            currency=data.commission_currency,
        )
    )
    await db.flush()
    await db.refresh(offer)
    await record_offer_created(
        db,
        offer,
        audit_context_from_http(request, session_data),
        source_operation="offers.create",
    )
    return offer_public_fields(offer)


@router.get("/{offer_id}")
async def get_offer(
    offer_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
    days: int | None = Query(default=None, ge=1, le=366),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await _get_business_offer(db, offer_id, business_id)
    date_range = resolve_query_range(date_from, date_to, timezone_name, days, default_days=7)
    stats = await offer_stats(db, offer.id, date_range=date_range)
    series = await offer_timeseries(db, offer.id, date_range=date_range)
    approved_conversions = int(
        await db.scalar(
            select(func.count(Conversion.id)).where(
                Conversion.offer_id == offer.id,
                Conversion.status.in_(["approved", "paid"]),
                Conversion.created_at >= date_range.start,
                Conversion.created_at <= date_range.end,
            )
        )
        or 0
    )

    access_rows = (
        await db.execute(partner_access_query().where(OfferPartnerAccess.offer_id == offer.id))
    ).all()

    partners = []
    pending = []
    top = []
    for access, profile, user in access_rows:
        partner_stats = await offer_stats(db, offer.id, partner_id=profile.id, date_range=date_range)
        item = serialize_business_partner_access(access, profile, user, partner_stats)
        partners.append(item)
        if access.status == "pending":
            pending.append(item)
        if access.status == "approved":
            top.append(item)
    top.sort(key=lambda row: row["conversions"], reverse=True)

    links_count = int(
        await db.scalar(
            select(func.count(TrackingLink.id)).where(
                TrackingLink.offer_id == offer.id,
                TrackingLink.status == "ACTIVE",
            )
        )
        or 0
    )
    promotion_rows = (
        await db.execute(
            select(TrackingLink, PartnerProfile, User)
            .join(PartnerProfile, TrackingLink.partner_id == PartnerProfile.id)
            .join(User, PartnerProfile.user_id == User.id)
            .where(TrackingLink.offer_id == offer.id)
            .order_by(TrackingLink.created_at.desc())
        )
    ).all()
    stats_by_link = await offer_link_stats(db, offer.id, date_range=date_range)
    own_stats = await offer_source_stats(db, offer.id, business_owned=True, date_range=date_range)
    partner_stats = await offer_source_stats(db, offer.id, business_owned=False, date_range=date_range)
    promotion_links = []
    for link, profile, user in promotion_rows:
        link_stats = stats_by_link.get(link.id, {"clicks": 0, "conversions": 0})
        public_name = partner_public_display_name_from(profile, user)
        promotion_links.append(
            {
                "id": link.id,
                "name": link.name or public_name,
                "url": f"https://go.refiq.ru/{link.short_code}",
                "short_code": link.short_code,
                "destination_url": link.destination_url,
                "partner_name": public_name,
                "traffic_source": link.traffic_source,
                "status": link.status,
                "clicks": link_stats["clicks"],
                "conversions": link_stats["conversions"],
            }
        )

    product = None
    if offer.product_id:
        product = (
            await db.execute(select(Product).where(Product.id == offer.product_id))
        ).scalar_one_or_none()

    warnings = []
    if offer.status == "paused":
        warnings.append("Оффер приостановлен: новый трафик и подключения остановлены.")
    if offer.status == "closing":
        warnings.append("Оффер закрывается. Новые партнёры не подключаются.")
    if offer.status == "archived":
        warnings.append("Оффер в архиве и скрыт из каталога.")
    if pending:
        warnings.append(f"Есть заявки партнёров, ожидающие решения: {len(pending)}.")

    return {
        **offer_public_fields(offer),
        "product_url": product.url if product else None,
        "kpis": {**stats, "approved_conversions": approved_conversions},
        "timeseries": series,
        "partners": partners,
        "pending_applications": pending,
        "top_partners": top[:5],
        "active_partners": sum(1 for row in partners if row["status"] == "approved"),
        "active_links": links_count,
        "promotion_links": promotion_links,
        "traffic_split": {
            "own": own_stats,
            "partner": partner_stats,
        },
        "warnings": warnings,
    }


@router.patch("/{offer_id}")
async def update_offer(
    offer_id: str,
    data: UpdateOfferRequest,
    request: Request,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await _get_business_offer(db, offer_id, business_id)
    before = snapshot_offer(offer)
    payload = data.model_dump(exclude_unset=True)

    if payload.get("status") and payload["status"] not in VALID_STATUSES:
        raise ForbiddenError("Invalid offer status")
    if "access_policy" in payload:
        payload["access_policy"] = validate_access_policy(payload["access_policy"])
    if "conversion_type" in payload:
        payload["conversion_type"] = validate_conversion_type(payload["conversion_type"])
    if "attribution_window_days" in payload:
        payload["attribution_window_days"] = validate_attribution_window_days(payload["attribution_window_days"])
    if "hold_period_days" in payload:
        payload["hold_period_days"] = validate_hold_period_days(payload["hold_period_days"])
    if "geo" in payload:
        payload["geo"] = serialize_geo(validate_geo_codes(payload["geo"]))
    if "allowed_traffic" in payload:
        payload["allowed_traffic"] = validate_allowed_traffic(payload["allowed_traffic"])
        payload["forbidden_traffic"] = []
    if "description" in payload:
        payload["description"] = validate_offer_description(payload["description"])
    if "partner_notes" in payload:
        payload["partner_notes"] = normalize_partner_notes(payload["partner_notes"])
    category = payload.pop("category", None)
    category_id = payload.pop("category_id", None)
    if category is not None or category_id is not None:
        category_row = await _resolve_category(db, category, category_id)
        payload["category"] = category_row.code
        payload["category_id"] = category_row.id

    product_url = payload.pop("product_url", None)
    commission_type = payload.pop("commission_type", None)
    commission_value = payload.pop("commission_value", None)
    commission_currency = payload.pop("commission_currency", None)
    if commission_type is not None or commission_value is not None:
        current = offer.commission_rules[0] if offer.commission_rules else None
        validate_commission(
            commission_type or (current.type if current else "percent"),
            commission_value if commission_value is not None else (float(current.value) if current else None),
        )

    for key, value in payload.items():
        setattr(offer, key, value)

    await apply_commission_update(db, offer, commission_type, commission_value, commission_currency)

    if product_url is not None and offer.product_id:
        product = (
            await db.execute(select(Product).where(Product.id == offer.product_id))
        ).scalar_one_or_none()
        if product:
            product.url = product_url

    await record_offer_mutations(
        db,
        offer,
        before,
        snapshot_offer(offer),
        audit_context_from_http(request, session_data),
        source_operation="offers.update",
    )
    return {"status": "ok"}


@router.post("/{offer_id}/partners/{access_id}/approve")
async def approve_partner(
    offer_id: str,
    access_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await _get_business_offer(db, offer_id, business_id)
    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.id == parse_id(access_id),
                OfferPartnerAccess.offer_id == offer.id,
            )
        )
    ).scalar_one_or_none()
    if not access:
        raise NotFoundError("Application")
    from app.modules.finance.self_deal import assert_not_self_deal

    await assert_not_self_deal(db, offer=offer, partner_id=access.partner_id, user_id=session_data.get("user_id"))
    access.status = "approved"
    access.approved_at = datetime.now(timezone.utc)
    access.rejection_reason = None
    await ensure_business_partner(db, offer.business_id, access.partner_id, "active")
    return {"status": "approved"}


@router.post("/{offer_id}/partners/{access_id}/reject")
async def reject_partner(
    offer_id: str,
    access_id: str,
    data: RejectPartnerRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await _get_business_offer(db, offer_id, business_id)
    access = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.id == parse_id(access_id),
                OfferPartnerAccess.offer_id == offer.id,
            )
        )
    ).scalar_one_or_none()
    if not access:
        raise NotFoundError("Application")
    if access.status != "pending":
        raise ForbiddenError("Only a pending request can be rejected")
    reason = (data.reason or "").strip()
    if not reason:
        raise AppError("INVALID_REJECTION_REASON", "Укажите причину отказа", 400)
    if len(reason) > 1000:
        raise AppError("INVALID_REJECTION_REASON", "Максимальная длина — 1000 символов", 400)
    access.status = "rejected"
    access.rejection_reason = reason
    return {"status": "rejected"}


@router.post("/{offer_id}/invite")
async def invite_partner(
    offer_id: str,
    data: InvitePartnerRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    offer = await _get_business_offer(db, offer_id, business_id)
    if offer.status in {"archived", "draft"}:
        raise ForbiddenError("Cannot invite partners to this offer")

    profile = None
    if data.partner_id:
        profile = (
            await db.execute(select(PartnerProfile).where(PartnerProfile.id == data.partner_id))
        ).scalar_one_or_none()
    elif data.email:
        profile = (
            await db.execute(
                select(PartnerProfile)
                .join(User, PartnerProfile.user_id == User.id)
                .where(func.lower(User.email) == data.email.strip().lower())
            )
        ).scalar_one_or_none()
    if not profile:
        raise NotFoundError("Partner")

    from app.modules.finance.self_deal import assert_not_self_deal

    await assert_not_self_deal(db, offer=offer, partner_id=profile.id, user_id=session_data.get("user_id"))

    existing = (
        await db.execute(
            select(OfferPartnerAccess).where(
                OfferPartnerAccess.offer_id == offer.id,
                OfferPartnerAccess.partner_id == profile.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.status = "approved"
        existing.source = "invitation"
        existing.approved_at = datetime.now(timezone.utc)
    else:
        db.add(
            OfferPartnerAccess(
                offer_id=offer.id,
                partner_id=profile.id,
                status="approved",
                source="invitation",
                approved_at=datetime.now(timezone.utc),
            )
        )
    await ensure_business_partner(db, offer.business_id, profile.id, "active")
    return {"status": "invited"}
