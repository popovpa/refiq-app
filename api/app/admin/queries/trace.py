from app.admin.queries.common import iso
from app.admin.services.clickstream import ClickstreamProvider, get_clickstream_provider
from app.core.exceptions import NotFoundError
from app.modules.businesses.models import Business
from app.modules.campaigns.models import Campaign
from app.modules.commissions.models import Commission
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.partners.models import PartnerProfile
from app.modules.payouts.models import Payout, PayoutItem
from app.modules.postback.attempt import PostbackAttempt, PostbackAttemptResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


REASON_MESSAGES = {
    "RQCID_NOT_FOUND": "Клик с этим rqcid не найден.",
    "INVALID_TOKEN": "Токен Postback недействителен или отсутствует.",
    "DUPLICATE_CONVERSION": "Конверсия для этого rqcid уже существует.",
    "INVALID_AMOUNT": "Некорректная сумма в Postback.",
    "OFFER_INACTIVE": "Оффер не активен.",
    "ATTRIBUTION_WINDOW_EXPIRED": "Postback отклонён: истекло окно атрибуции.",
    "TRACKING_LINK_INACTIVE": "Ссылка не активна.",
    "PARTNER_BLOCKED": "Партнёр заблокирован.",
    "NO_CLICK": "Клик для этого rqcid не найден.",
    "OFFER_MISMATCH": "Бизнес в Postback не совпадает с оффером клика.",
    "PARTNER_INACTIVE": "Партнёр неактивен.",
    "ATTRIBUTED": "Атрибуция выполнена.",
    "CALCULATED": "Комиссия рассчитана.",
    "NOT_APPLICABLE": "Не применяется.",
    "WAITING_APPROVAL": "Ожидает одобрения.",
    "REJECTED": "Отклонено.",
}


def _step(key: str, label: str, status: str, *, at=None, reason: str | None = None, entity=None) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "at": iso(at) if at and not isinstance(at, str) else at,
        "reason_code": reason,
        "entity": entity,
    }


async def build_trace(db: AsyncSession, rqcid: str, provider: ClickstreamProvider | None = None) -> dict:
    provider = provider or get_clickstream_provider()
    click_row = (
        await db.execute(
            select(Click, TrackingLink, Offer, Business, PartnerProfile, Campaign)
            .join(TrackingLink, TrackingLink.id == Click.tracking_link_id)
            .join(Offer, Offer.id == TrackingLink.offer_id)
            .join(Business, Business.id == Offer.business_id)
            .join(PartnerProfile, PartnerProfile.id == TrackingLink.partner_id)
            .outerjoin(Campaign, Campaign.id == TrackingLink.campaign_id)
            .where(Click.rqcid == rqcid)
        )
    ).first()
    if not click_row:
        conversion_only = (
            await db.execute(select(Conversion).where(Conversion.click_id == rqcid))
        ).scalar_one_or_none()
        if not conversion_only:
            raise NotFoundError("Trace")
        raise NotFoundError("Click")

    click, link, offer, business, partner, campaign = click_row
    conversion = (
        await db.execute(select(Conversion).where(Conversion.click_id == rqcid))
    ).scalar_one_or_none()
    attempts = (
        await db.execute(
            select(PostbackAttempt).where(PostbackAttempt.rqcid == rqcid).order_by(PostbackAttempt.id.asc())
        )
    ).scalars().all()
    commission = None
    payout = None
    if conversion:
        commission = (
            await db.execute(select(Commission).where(Commission.conversion_id == conversion.id))
        ).scalar_one_or_none()
        if commission:
            payout_id = (
                await db.execute(select(PayoutItem.payout_id).where(PayoutItem.commission_id == commission.id))
            ).scalar_one_or_none()
            if payout_id:
                payout = await db.get(Payout, payout_id)

    sdk_events = await provider.events_for_rqcid(rqcid)
    last_attempt = attempts[-1] if attempts else None
    rejected = last_attempt and last_attempt.result == PostbackAttemptResult.REJECTED
    duplicate = last_attempt and last_attempt.result == PostbackAttemptResult.DUPLICATE
    accepted = last_attempt and last_attempt.result == PostbackAttemptResult.ACCEPTED

    tracking = [
        _step("click", "Клик по ссылке", "ok", at=click.created_at, entity={"type": "click", "id": click.id}),
        _step("redirect", "Редирект", "ok", at=click.created_at, entity={"type": "tracking_link", "id": link.id}),
    ]
    behavior = []
    if sdk_events:
        behavior.append(_step("sdk_detected", "Активность SDK", "ok", at=sdk_events[0].get("at")))
        for event in sdk_events:
            behavior.append(
                _step(event.get("name") or "event", event.get("name") or "Событие SDK", "ok", at=event.get("at"))
            )
    else:
        behavior.append(
            _step(
                "sdk_detected",
                "Активность SDK",
                "unavailable",
                reason="NOT_APPLICABLE",
            )
        )

    conversion_steps = []
    if last_attempt:
        conversion_steps.append(
            _step(
                "postback_received",
                "Postback получен" if not rejected else "Postback отклонён",
                "ok" if not rejected else "error",
                at=last_attempt.received_at,
                reason=last_attempt.reason_code,
                entity={"type": "postback", "id": last_attempt.id},
            )
        )
    else:
        conversion_steps.append(_step("postback_received", "Postback получен", "pending"))

    if conversion:
        conversion_steps.append(
            _step("attribution", "Атрибуция успешна", "ok", reason="ATTRIBUTED", at=conversion.created_at)
        )
        conversion_steps.append(
            _step(
                "conversion_created",
                "Конверсия создана",
                "ok",
                at=conversion.created_at,
                entity={"type": "conversion", "id": conversion.id},
            )
        )
    elif rejected:
        conversion_steps.append(
            _step(
                "attribution",
                "Атрибуция не удалась",
                "error",
                reason=last_attempt.reason_code if last_attempt else "REJECTED",
            )
        )
        conversion_steps.append(_step("conversion_created", "Конверсия создана", "missing"))
    else:
        conversion_steps.append(_step("attribution", "Атрибуция", "pending"))
        conversion_steps.append(_step("conversion_created", "Конверсия создана", "pending"))

    finance = []
    if commission:
        finance.append(
            _step(
                "commission_calculated",
                "Комиссия рассчитана",
                "ok",
                reason="CALCULATED",
                entity={"type": "commission", "id": commission.id},
            )
        )
        finance.append(
            _step(
                "commission_status",
                f"Комиссия: {commission.status}",
                "ok" if commission.status != "cancelled" else "error",
                reason=commission.status.upper(),
            )
        )
    else:
        finance.append(_step("commission_calculated", "Комиссия рассчитана", "missing" if conversion or rejected else "pending"))

    if payout:
        finance.append(
            _step(
                "payout_created",
                "Выплата создана",
                "ok",
                entity={"type": "payout", "id": payout.id},
            )
        )
        finance.append(
            _step(
                "payout_paid",
                "Выплата выплачена" if payout.status == "paid" else "Выплата ожидает",
                "ok" if payout.status == "paid" else "pending",
            )
        )
    else:
        finance.append(_step("payout_created", "Выплата ожидает", "pending" if conversion else "missing"))

    traffic_ok = True
    sdk_ok = bool(sdk_events) or True  # unavailable is not a failure
    postback_status = "ok" if accepted or duplicate or conversion else ("failed" if rejected else "missing")
    conversion_status = "ok" if conversion else ("not_created" if rejected or last_attempt else "not_created")
    commission_status = "ok" if commission else "not_created"

    problem_code = None
    if rejected and last_attempt:
        problem_code = last_attempt.reason_code
    elif not click:
        problem_code = "NO_CLICK"

    summary = {
        "traffic": "OK" if traffic_ok else "Ошибка",
        "sdk_tracking": "OK" if sdk_events else "Недоступно",
        "postback": "OK" if postback_status == "ok" else ("Ошибка" if postback_status == "failed" else "Не получен"),
        "conversion": "Создана" if conversion else "Не создана",
        "commission": "Создана" if commission else "Не создана",
        "problem_code": problem_code,
        "problem": REASON_MESSAGES.get(problem_code or "", None),
    }

    return {
        "rqcid": rqcid,
        "context": {
            "business": {"id": business.id, "name": business.name},
            "offer": {"id": offer.id, "name": offer.name},
            "partner": {"id": partner.id, "name": partner.display_name},
            "tracking_link": {"id": link.id, "short_code": link.short_code, "status": link.status},
            "campaign": {"id": campaign.id, "name": campaign.name} if campaign else None,
            "created_at": iso(click.created_at),
            "status": conversion.status if conversion else (last_attempt.result if last_attempt else "CLICK_ONLY"),
        },
        "summary": summary,
        "timeline": {
            "tracking": tracking,
            "behavior": behavior,
            "conversion": conversion_steps,
            "finance": finance,
        },
        "clickstream_available": provider.available,
    }
