from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select, func
from app.core.ids import parse_id

from app.common.date_range import resolve_query_range
from app.modules.businesses.dashboard import build_business_dashboard

from app.core.database import get_db
from app.core.permissions import require_business_role
from app.core.exceptions import AppError, NotFoundError, ForbiddenError
from app.modules.campaigns.models import Campaign
from app.modules.links.models import TrackingLink
from app.modules.conversions.models import Conversion
from app.modules.partners.models import PartnerProfile, BusinessPartner
from app.modules.partners.privacy import (
    looks_like_contact,
    partner_public_display_name_from,
    strip_partner_contact_fields,
)
from app.modules.businesses.models import BusinessMembership
from app.modules.offers.models import Offer, OfferPartnerAccess
from app.modules.users.models import User
from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified

router = APIRouter()


@router.get("/dashboard")
async def business_dashboard(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
    days: int | None = Query(default=None, ge=1, le=366),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
):
    business_id = parse_id(session_data["active_business_id"])
    date_range = resolve_query_range(date_from, date_to, timezone_name, days)
    return await build_business_dashboard(db, business_id, days=days, date_range=date_range)


@router.get("/partners")
async def list_partners(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    query = (
        select(BusinessPartner, PartnerProfile, User)
        .join(PartnerProfile, BusinessPartner.partner_id == PartnerProfile.id)
        .join(User, PartnerProfile.user_id == User.id)
        .where(BusinessPartner.business_id == business_id)
    )

    if status:
        query = query.where(BusinessPartner.status == status)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()
    partner_ids = [row.BusinessPartner.partner_id for row in rows]

    offers_counts: dict = {}
    conversions_counts: dict = {}
    earned_totals: dict = {}

    if partner_ids:
        offers_result = await db.execute(
            select(
                OfferPartnerAccess.partner_id,
                func.count(OfferPartnerAccess.id),
            )
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(
                Offer.business_id == business_id,
                OfferPartnerAccess.partner_id.in_(partner_ids),
                OfferPartnerAccess.status == "approved",
            )
            .group_by(OfferPartnerAccess.partner_id)
        )
        offers_counts = {pid: cnt for pid, cnt in offers_result.all()}

        conv_result = await db.execute(
            select(
                Conversion.partner_id,
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.commission_amount), 0),
            )
            .where(
                Conversion.business_id == business_id,
                Conversion.partner_id.in_(partner_ids),
                Conversion.status.in_(["approved", "paid"]),
            )
            .group_by(Conversion.partner_id)
        )
        for pid, cnt, earned in conv_result.all():
            conversions_counts[pid] = cnt
            earned_totals[pid] = float(earned)

    items = [
        strip_partner_contact_fields(
            {
                "id": row.BusinessPartner.id,
                "partner_id": row.BusinessPartner.partner_id,
                "display_name": partner_public_display_name_from(row.PartnerProfile, row.User),
                "status": row.BusinessPartner.status,
                "offers_count": offers_counts.get(row.BusinessPartner.partner_id, 0),
                "total_conversions": conversions_counts.get(row.BusinessPartner.partner_id, 0),
                "total_earned": earned_totals.get(row.BusinessPartner.partner_id, 0),
                "joined_at": row.BusinessPartner.created_at.isoformat(),
            }
        )
        for row in rows
    ]

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.get("/partners/{partner_id}")
async def get_partner(
    partner_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    try:
        pid = parse_id(partner_id)
    except ValueError:
        raise NotFoundError("Partner")
    related = (
        await db.execute(
            select(OfferPartnerAccess.id)
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(Offer.business_id == business_id, OfferPartnerAccess.partner_id == pid)
            .limit(1)
        )
    ).scalar_one_or_none()
    if related is None:
        bp_exists = (
            await db.execute(
                select(BusinessPartner.id).where(
                    BusinessPartner.business_id == business_id,
                    BusinessPartner.partner_id == pid,
                )
            )
        ).scalar_one_or_none()
        if bp_exists is None:
            raise NotFoundError("Partner")

    row = (
        await db.execute(
            select(PartnerProfile, User, BusinessPartner)
            .join(User, PartnerProfile.user_id == User.id)
            .outerjoin(
                BusinessPartner,
                and_(
                    BusinessPartner.partner_id == PartnerProfile.id,
                    BusinessPartner.business_id == business_id,
                ),
            )
            .where(PartnerProfile.id == pid)
        )
    ).first()
    if not row:
        raise NotFoundError("Partner")
    profile, user, membership = row
    description = (profile.description or "").strip() or None
    if description and looks_like_contact(description):
        description = None
    offers_count = int(
        await db.scalar(
            select(func.count(OfferPartnerAccess.id))
            .join(Offer, OfferPartnerAccess.offer_id == Offer.id)
            .where(
                Offer.business_id == business_id,
                OfferPartnerAccess.partner_id == pid,
                OfferPartnerAccess.status == "approved",
            )
        )
        or 0
    )
    created_at = membership.created_at if membership else profile.created_at
    return strip_partner_contact_fields(
        {
            "partner_id": profile.id,
            "display_name": partner_public_display_name_from(profile, user),
            "description": description,
            "status": membership.status if membership else profile.status,
            "created_at": created_at.isoformat() if created_at else None,
            "offers_count": offers_count,
        }
    )


@router.post("/partners/{partner_id}/approve")
async def approve_partner(
    partner_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(
        select(BusinessPartner).where(
            BusinessPartner.business_id == business_id,
            BusinessPartner.partner_id == parse_id(partner_id),
        )
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise NotFoundError("Partner")
    bp.status = "active"
    return {"status": "ok"}


@router.post("/partners/{partner_id}/block")
async def block_partner(
    partner_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(
        select(BusinessPartner).where(
            BusinessPartner.business_id == business_id,
            BusinessPartner.partner_id == parse_id(partner_id),
        )
    )
    bp = result.scalar_one_or_none()
    if not bp:
        raise NotFoundError("Partner")
    bp.status = "blocked"
    return {"status": "ok"}


@router.get("/conversions")
async def list_business_conversions(
    status: str | None = None,
    source_owner: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    query = (
        select(
            Conversion,
            Offer.name.label("offer_name"),
            PartnerProfile,
            User,
            Campaign.name.label("campaign_name"),
            TrackingLink,
        )
        .join(Offer, Conversion.offer_id == Offer.id)
        .outerjoin(PartnerProfile, Conversion.partner_id == PartnerProfile.id)
        .outerjoin(User, PartnerProfile.user_id == User.id)
        .outerjoin(TrackingLink, Conversion.tracking_link_id == TrackingLink.id)
        .outerjoin(Campaign, TrackingLink.campaign_id == Campaign.id)
        .where(Conversion.business_id == business_id)
    )
    count_filters = [Conversion.business_id == business_id]
    if status:
        query = query.where(Conversion.status == status)
        count_filters.append(Conversion.status == status)
    if source_owner == "business":
        query = query.where(TrackingLink.business_id.is_not(None))
        count_filters.append(TrackingLink.business_id.is_not(None))
    elif source_owner == "partner":
        query = query.where(TrackingLink.partner_id.is_not(None))
        count_filters.append(TrackingLink.partner_id.is_not(None))
    if date_from is not None and date_to is not None:
        date_range = resolve_query_range(date_from, date_to, timezone_name, None)
        query = query.where(
            Conversion.created_at >= date_range.start,
            Conversion.created_at <= date_range.end,
        )
        count_filters.extend(
            [Conversion.created_at >= date_range.start, Conversion.created_at <= date_range.end]
        )
    query = query.order_by(Conversion.created_at.desc())

    count_query = select(func.count(Conversion.id)).where(*count_filters)
    if source_owner in {"business", "partner"}:
        count_query = count_query.join(TrackingLink, Conversion.tracking_link_id == TrackingLink.id)
    total = await db.scalar(count_query)

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    items = [
        {
            "id": row.Conversion.id,
            "offer_id": row.Conversion.offer_id,
            "offer_name": row.offer_name,
            "partner_id": row.Conversion.partner_id,
            "partner_name": (
                partner_public_display_name_from(row.PartnerProfile, row.User)
                if row.PartnerProfile is not None
                else None
            ),
            "campaign_name": row.campaign_name,
            "source_owner": (
                "business"
                if row.TrackingLink is not None and row.TrackingLink.business_id
                else "partner"
            ),
            "click_id": row.Conversion.click_id,
            "external_id": row.Conversion.external_id,
            "amount": float(row.Conversion.amount),
            "currency": row.Conversion.currency,
            "commission_amount": float(row.Conversion.commission_amount),
            "status": row.Conversion.status,
            "converted_at": row.Conversion.converted_at.isoformat() if row.Conversion.converted_at else None,
            "created_at": row.Conversion.created_at.isoformat(),
        }
        for row in result.all()
    ]

    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.post("/conversions/{conversion_id}/approve")
async def approve_conversion(
    conversion_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(
        select(Conversion).where(
            Conversion.id == parse_id(conversion_id),
            Conversion.business_id == business_id,
        )
    )
    conversion = result.scalar_one_or_none()
    if not conversion:
        raise NotFoundError("Conversion")
    if conversion.status != "pending":
        raise AppError(code="INVALID_STATUS", message="Conversion is not pending", status_code=400)

    from datetime import datetime, timedelta, timezone
    conversion.status = "approved"
    conversion.approved_at = datetime.now(timezone.utc)
    snapshot = int(conversion.hold_period_days_snapshot or 0)
    conversion.available_at = conversion.approved_at + timedelta(days=snapshot)

    if conversion.partner_id is not None:
        from app.modules.commissions.models import Commission
        commission = Commission(
            conversion_id=conversion.id,
            business_id=business_id,
            partner_id=conversion.partner_id,
            amount=conversion.commission_amount,
            currency=conversion.currency,
            status="approved",
            available_at=conversion.available_at,
        )
        db.add(commission)

    return {"status": "ok"}


@router.post("/conversions/{conversion_id}/reject")
async def reject_conversion(
    conversion_id: str,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(
        select(Conversion).where(
            Conversion.id == parse_id(conversion_id),
            Conversion.business_id == business_id,
        )
    )
    conversion = result.scalar_one_or_none()
    if not conversion:
        raise NotFoundError("Conversion")
    conversion.status = "rejected"
    return {"status": "ok"}


@router.get("/payouts")
async def list_business_payouts(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.commissions.models import Commission
    business_id = parse_id(session_data["active_business_id"])

    payable = await db.scalar(
        select(func.coalesce(func.sum(Commission.amount), 0)).where(
            Commission.business_id == business_id,
            Commission.status == "approved",
        )
    )

    return {
        "payable_amount": float(payable or 0),
        "pending": [],
        "processing": [],
        "paid": [],
    }


VALID_ACCESS_POLICIES = {"open", "approval", "invite_only"}
VALID_CURRENCIES = {"RUB", "USD", "EUR"}
JSONB_SETTINGS_KEYS = {
    "website",
    "category",
    "work_email",
    "phone",
    "description",
    "logo_url",
    "default_attribution_window_days",
    "default_access_policy",
    "default_confirmation_days",
}


class BusinessSettingsUpdate(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    country: str | None = None
    currency: str | None = None
    website: str | None = None
    category: str | None = None
    work_email: str | None = None
    phone: str | None = None
    description: str | None = None
    logo_url: str | None = None
    default_attribution_window_days: int | None = Field(default=None, ge=1, le=365)
    default_access_policy: str | None = None
    default_confirmation_days: int | None = Field(default=None, ge=0, le=365)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _settings_dict(row) -> dict:
    return dict(row.settings or {}) if row else {}


def _settings_response(business, extra: dict) -> dict:
    access = extra.get("default_access_policy")
    if access not in VALID_ACCESS_POLICIES:
        access = "approval"
    return {
        "id": business.id,
        "name": business.name,
        "legal_name": business.legal_name,
        "country": business.country,
        "currency": business.currency or "RUB",
        "website": extra.get("website") or "",
        "category": extra.get("category") or "",
        "work_email": extra.get("work_email") or "",
        "phone": extra.get("phone") or "",
        "description": extra.get("description") or "",
        "logo_url": extra.get("logo_url") or None,
        "default_attribution_window_days": extra.get("default_attribution_window_days") or 30,
        "default_access_policy": access,
        "default_confirmation_days": extra.get("default_confirmation_days") if extra.get("default_confirmation_days") is not None else 30,
    }


async def _load_business_settings_row(db: AsyncSession, business_id: int):
    from app.modules.system.models import BusinessSettings
    result = await db.execute(select(BusinessSettings).where(BusinessSettings.business_id == business_id))
    return result.scalar_one_or_none()


@router.get("/settings")
async def get_business_settings(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.businesses.models import Business
    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise NotFoundError("Business")
    row = await _load_business_settings_row(db, business_id)
    return _settings_response(business, _settings_dict(row))


@router.patch("/settings")
async def update_business_settings(
    data: BusinessSettingsUpdate,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.businesses.models import Business
    from app.modules.system.models import BusinessSettings

    business_id = parse_id(session_data["active_business_id"])
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise NotFoundError("Business")

    payload = data.model_dump(exclude_unset=True)

    if "name" in payload:
        name = (payload["name"] or "").strip()
        if not name:
            raise AppError(code="INVALID_NAME", message="Укажите название компании", status_code=400)
        business.name = name
    if "legal_name" in payload:
        business.legal_name = _normalize_optional_text(payload["legal_name"])
    if "country" in payload:
        country = _normalize_optional_text(payload["country"])
        business.country = country.upper() if country else None
    if "currency" in payload:
        currency = (payload["currency"] or "").strip().upper()
        if currency not in VALID_CURRENCIES:
            raise AppError(code="INVALID_CURRENCY", message="Некорректная валюта", status_code=400)
        business.currency = currency
    if "default_access_policy" in payload:
        access = payload["default_access_policy"]
        if access not in VALID_ACCESS_POLICIES:
            raise AppError(code="INVALID_ACCESS_POLICY", message="Некорректный тип доступа", status_code=400)

    json_updates = {key: payload[key] for key in JSONB_SETTINGS_KEYS if key in payload}
    if json_updates:
        row = await _load_business_settings_row(db, business_id)
        if not row:
            row = BusinessSettings(business_id=business_id, settings={})
            db.add(row)
            await db.flush()
        settings = _settings_dict(row)
        for key, value in json_updates.items():
            if key in {"website", "category", "work_email", "phone", "description"}:
                settings[key] = _normalize_optional_text(value) if isinstance(value, str) else value
            elif key == "logo_url":
                settings[key] = value or None
            elif key == "default_access_policy":
                settings[key] = value
            else:
                settings[key] = value
        row.settings = settings
        flag_modified(row, "settings")

    return {"status": "ok"}
