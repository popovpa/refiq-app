from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.exceptions import AppError
from app.modules.conversions.models import Conversion
from app.modules.links.models import Click, TrackingLink
from app.modules.offers.models import Offer
from app.modules.postback.attempt import PostbackAttempt, PostbackAttemptResult
from app.modules.postback.auth_service import PostbackAuthenticationService
from app.modules.postback.dto import PostbackAccepted, PostbackRequest
from app.modules.postback.models import PostbackCredential
from app.modules.postback.repository import PostbackRepository
from app.modules.postback.validator import PostbackValidator, invalid_postback
from app.modules.promotion.attribution import resolve_conversion_attribution, within_attribution_window
from app.modules.system.audit import write_audit_log


class PostbackReject(Exception):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code


class PostbackService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = PostbackRepository(db)
        self.validator = PostbackValidator()
        self.auth = PostbackAuthenticationService(db)

    async def handle(self, authorization: str | None, payload: PostbackRequest) -> PostbackAccepted:
        try:
            credential = await self.auth.authenticate(authorization)
        except AppError:
            await self._record_independent(
                business_id=None,
                rqcid=getattr(payload, "rqcid", None),
                result=PostbackAttemptResult.REJECTED,
                reason_code="INVALID_TOKEN",
            )
            raise
        try:
            self.validator.validate_request(payload)
        except AppError:
            reason = "RQCID_NOT_FOUND" if not (payload.rqcid or "") else "INVALID_AMOUNT"
            await self._record_independent(
                business_id=credential.business_id,
                rqcid=payload.rqcid,
                result=PostbackAttemptResult.REJECTED,
                reason_code=reason,
            )
            raise invalid_postback()
        try:
            conversion, result, reason = await self._process(credential, payload)
        except PostbackReject as exc:
            await self._record_independent(
                business_id=credential.business_id,
                rqcid=payload.rqcid,
                result=PostbackAttemptResult.REJECTED,
                reason_code=exc.reason_code,
            )
            raise invalid_postback()
        self.db.add(
            PostbackAttempt(
                business_id=credential.business_id,
                rqcid=payload.rqcid,
                result=result,
                reason_code=reason,
                conversion_id=conversion.id,
            )
        )
        await self.repository.mark_success(credential)
        await write_audit_log(
            self.db,
            user_id=None,
            action="postback.received",
            resource_type="conversion",
            resource_id=str(conversion.id),
            details={"rqcid": payload.rqcid},
        )
        return PostbackAccepted()

    async def _process(
        self, credential: PostbackCredential, payload: PostbackRequest
    ) -> tuple[Conversion, str, str]:
        click = await self._load_click(payload.rqcid)
        if not click:
            raise PostbackReject("NO_CLICK")

        link = (
            await self.db.execute(select(TrackingLink).where(TrackingLink.id == click.tracking_link_id))
        ).scalar_one_or_none()
        if not link:
            raise PostbackReject("NO_CLICK")

        offer = (await self.db.execute(select(Offer).where(Offer.id == link.offer_id))).scalar_one_or_none()
        if not offer or offer.business_id != credential.business_id:
            raise PostbackReject("OFFER_MISMATCH")
        if not self._within_attribution_window(click, offer):
            raise PostbackReject("ATTRIBUTION_WINDOW_EXPIRED")

        existing = await self._existing_conversion(credential.business_id, payload.rqcid)
        if existing:
            return existing, PostbackAttemptResult.DUPLICATE, "DUPLICATE_CONVERSION"

        amount = Decimal(str(payload.amount if payload.amount is not None else 0))
        currency = (payload.currency or offer.currency or "RUB").upper()
        attributed = await resolve_conversion_attribution(self.db, click=click, link=link, offer=offer)
        commission = self._commission(offer, amount) if attributed.partner_id else Decimal("0.00")
        conversion = Conversion(
            business_id=credential.business_id,
            offer_id=link.offer_id,
            partner_id=attributed.partner_id,
            tracking_link_id=attributed.tracking_link_id,
            partner_tracking_link_id=attributed.partner_tracking_link_id,
            click_id=payload.rqcid,
            amount=float(amount),
            currency=currency,
            commission_amount=float(commission),
            status="pending",
            hold_period_days_snapshot=int(offer.hold_period_days or 0),
            converted_at=datetime.now(timezone.utc),
        )
        self.db.add(conversion)
        await self.db.flush()
        return conversion, PostbackAttemptResult.ACCEPTED, "ATTRIBUTED"

    async def _record_independent(
        self,
        *,
        business_id: int | None,
        rqcid: str | None,
        result: str,
        reason_code: str,
        conversion_id: int | None = None,
    ) -> None:
        factory = async_session_factory
        async with factory() as session:
            session.add(
                PostbackAttempt(
                    business_id=business_id,
                    rqcid=(rqcid or None),
                    result=result,
                    reason_code=reason_code,
                    conversion_id=conversion_id,
                )
            )
            if business_id and result == PostbackAttemptResult.REJECTED:
                from app.modules.notifications.service import NotificationService

                await NotificationService(session).notify_postback_failed(
                    business_id=business_id,
                    reason_code=reason_code,
                )
            await session.commit()

    async def _load_click(self, rqcid: str) -> Click | None:
        result = await self.db.execute(select(Click).where(Click.rqcid == rqcid))
        return result.scalar_one_or_none()

    async def _existing_conversion(self, business_id: int, rqcid: str) -> Conversion | None:
        result = await self.db.execute(
            select(Conversion).where(
                Conversion.business_id == business_id,
                Conversion.click_id == rqcid,
            )
        )
        return result.scalar_one_or_none()

    def _within_attribution_window(self, click: Click, offer: Offer) -> bool:
        return within_attribution_window(click, offer)

    def _commission(self, offer: Offer, amount: Decimal) -> Decimal:
        rules = offer.commission_rules or []
        if not rules:
            return Decimal("0.00")
        rule = rules[0]
        value = Decimal(str(rule.value))
        if rule.type == "percent":
            result = (amount * value) / Decimal("100")
        else:
            result = value
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
