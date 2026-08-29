from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CreativePolicyStatus, CreativeSource, CreativeStatus, CreativeType
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.modules.ai.usage.service import AiUsageService
from app.modules.creatives.models import Creative
from app.modules.creatives.policy import CreativePolicyValidator
from app.modules.brand_kits.service import get_brand_kit
from app.modules.offers.models import Offer


class CreativeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.policy = CreativePolicyValidator()

    async def list_for_business(self, offer: Offer) -> list[Creative]:
        result = await self.db.execute(
            select(Creative)
            .where(Creative.offer_id == offer.id, Creative.partner_id.is_(None))
            .order_by(Creative.id.desc())
        )
        return list(result.scalars().all())

    async def list_for_partner(self, offer: Offer, partner_id: int) -> list[Creative]:
        result = await self.db.execute(
            select(Creative)
            .where(
                Creative.offer_id == offer.id,
                or_(
                    Creative.partner_id == partner_id,
                    (Creative.partner_id.is_(None)) & (Creative.status == CreativeStatus.ACTIVE.value),
                ),
            )
            .order_by(Creative.id.desc())
        )
        return list(result.scalars().all())

    async def get_for_business(self, offer: Offer, creative_id: int) -> Creative:
        creative = await self._get(creative_id, offer.id)
        if creative.partner_id is not None:
            raise NotFoundError("Creative")
        return creative

    async def get_for_partner(self, offer: Offer, creative_id: int, partner_id: int) -> Creative:
        creative = await self._get(creative_id, offer.id)
        if creative.partner_id == partner_id:
            return creative
        if creative.partner_id is None and creative.status == CreativeStatus.ACTIVE.value:
            return creative
        raise NotFoundError("Creative")

    async def create(
        self,
        *,
        offer: Offer,
        user_id: int,
        partner_id: int | None,
        creative_type: str,
        source: str,
        status: str,
        title: str | None,
        text_content: dict | None,
        asset_id: int | None,
        language: str | None,
        channel: str | None,
        image_format: str | None,
        generation_id: str | None,
        selected_variant: str | None,
        campaign_id: int | None = None,
    ) -> Creative:
        brand_kit = await get_brand_kit(self.db, offer.business_id)
        policy = {"status": CreativePolicyStatus.VALID.value, "issues": []}
        if text_content:
            policy = self.policy.validate_text(
                text_content,
                offer=offer,
                brand_kit=brand_kit,
                require_cta=creative_type == CreativeType.SOCIAL_POST.value,
            )
            if status == CreativeStatus.ACTIVE.value and policy["status"] == CreativePolicyStatus.BLOCKED.value:
                raise AppError("CREATIVE_CONTENT_BLOCKED", "Creative violates promotion rules", 400)
        creative = Creative(
            offer_id=offer.id,
            created_by_user_id=user_id,
            partner_id=partner_id,
            campaign_id=campaign_id,
            type=creative_type,
            source=source,
            status=status,
            title=title,
            text_content=text_content,
            asset_id=asset_id,
            language=language or "ru",
            channel=channel,
            format=image_format,
            generation_id=generation_id,
            selected_variant=selected_variant,
            policy_status=policy["status"],
            policy_issues=policy["issues"],
        )
        self.db.add(creative)
        await self.db.flush()
        if generation_id:
            await self._feedback(
                generation_id,
                user_id,
                "ACCEPTED",
                selected_variant=selected_variant,
            )
        return creative

    async def update_content(
        self,
        creative: Creative,
        *,
        offer: Offer,
        user_id: int,
        title: str | None = None,
        text_content: dict | None = None,
        generation_id: str | None = None,
    ) -> Creative:
        if title is not None:
            creative.title = title
        if text_content is not None:
            creative.text_content = text_content
        brand_kit = await get_brand_kit(self.db, offer.business_id)
        if creative.text_content:
            policy = self.policy.validate_text(
                creative.text_content,
                offer=offer,
                brand_kit=brand_kit,
                require_cta=creative.type == CreativeType.SOCIAL_POST.value,
            )
            creative.policy_status = policy["status"]
            creative.policy_issues = policy["issues"]
            if (
                creative.status == CreativeStatus.ACTIVE.value
                and policy["status"] == CreativePolicyStatus.BLOCKED.value
            ):
                raise AppError("CREATIVE_CONTENT_BLOCKED", "Creative violates promotion rules", 400)
        if generation_id:
            creative.generation_id = generation_id
            await self._feedback(generation_id, user_id, "EDITED")
        creative.updated_at = datetime.now(timezone.utc)
        return creative

    async def publish(self, creative: Creative, *, offer: Offer, user_id: int) -> Creative:
        if creative.partner_id is not None:
            raise ForbiddenError("Only business creatives can be published to partners")
        if creative.status == CreativeStatus.ARCHIVED.value:
            raise AppError("CREATIVE_ARCHIVED", "Archived creative cannot be published", 400)
        if creative.policy_status == CreativePolicyStatus.BLOCKED.value:
            raise AppError("CREATIVE_CONTENT_BLOCKED", "Creative violates promotion rules", 400)
        brand_kit = await get_brand_kit(self.db, offer.business_id)
        if creative.text_content:
            policy = self.policy.validate_text(
                creative.text_content,
                offer=offer,
                brand_kit=brand_kit,
                require_cta=creative.type == CreativeType.SOCIAL_POST.value,
            )
            creative.policy_status = policy["status"]
            creative.policy_issues = policy["issues"]
            if policy["status"] == CreativePolicyStatus.BLOCKED.value:
                raise AppError("CREATIVE_CONTENT_BLOCKED", "Creative violates promotion rules", 400)
        creative.status = CreativeStatus.ACTIVE.value
        creative.updated_at = datetime.now(timezone.utc)
        if creative.generation_id:
            await self._feedback(creative.generation_id, user_id, "PUBLISHED")
        return creative

    async def unpublish(self, creative: Creative) -> Creative:
        if creative.status == CreativeStatus.ARCHIVED.value:
            raise AppError("CREATIVE_ARCHIVED", "Archived creative cannot be unpublished", 400)
        creative.status = CreativeStatus.DRAFT.value
        creative.updated_at = datetime.now(timezone.utc)
        return creative

    async def delete(self, creative: Creative) -> None:
        from app.modules.assets.models import Asset
        from app.modules.assets.service import AssetService
        from app.modules.creatives.promo_runs import detach_creative_from_runs

        await detach_creative_from_runs(self.db, offer_id=creative.offer_id, creative_id=creative.id)
        asset_id = creative.asset_id
        await self.db.delete(creative)
        await self.db.flush()
        if asset_id:
            asset = (await self.db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
            if asset:
                await AssetService(self.db).delete_asset(asset)

    async def archive(self, creative: Creative) -> Creative:
        creative.status = CreativeStatus.ARCHIVED.value
        creative.updated_at = datetime.now(timezone.utc)
        return creative

    async def _get(self, creative_id: int, offer_id: int) -> Creative:
        creative = (
            await self.db.execute(
                select(Creative).where(Creative.id == creative_id, Creative.offer_id == offer_id)
            )
        ).scalar_one_or_none()
        if not creative:
            raise NotFoundError("Creative")
        return creative

    async def _feedback(
        self,
        generation_id: str,
        user_id: int,
        outcome: str,
        *,
        selected_variant: str | None = None,
    ) -> None:
        try:
            usage = await AiUsageService(self.db).record_feedback(
                generation_id,
                user_id=user_id,
                outcome=outcome,
                accepted_fields_count=1,
            )
            if selected_variant:
                metadata = dict(usage.provider_metadata or {})
                metadata["selected_variant"] = selected_variant
                usage.provider_metadata = metadata
        except Exception:
            return
