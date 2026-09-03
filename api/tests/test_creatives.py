import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CreativeSource, CreativeStatus, CreativeType
from app.main import app as fastapi_app
from app.modules.ai.capabilities import Operation
from app.modules.ai.context.offer_context import OfferPromotionContextBuilder
from app.modules.ai.jobs import DeferredJobRunner
from app.modules.ai.providers.fake import FakeTextGenerationProvider
from app.modules.ai.resolver import get_fake_image_provider, get_fake_provider
from app.modules.ai.usage.models import AiUsage
from app.modules.assets.models import Asset
from app.modules.brand_kits.models import BrandKit
from app.modules.creatives.models import Creative
from app.modules.creatives.policy import CreativePolicyValidator
from app.modules.offers.models import Offer
from tests.helpers import become_partner, register_business, register_user

TEXT_VARIANTS = {
    "variants": [
        {
            "kind": "short",
            "headline": "CRM без хаоса",
            "body": "Простая система для продаж.",
            "cta": "Попробовать",
        },
        {
            "kind": "expert",
            "headline": "CRM для команд",
            "body": "Учёт сделок и аналитика в одном месте.",
            "cta": "Узнать больше",
        },
        {
            "kind": "promotional",
            "headline": "Запустите партнёрку",
            "body": "Готовые офферы и выплаты без таблиц.",
            "cta": "Начать",
        },
    ]
}

SOCIAL_VARIANTS = {
    "variants": [
        {
            "kind": "short",
            "headline": "Пост в Telegram",
            "body": "Коротко о продукте.",
            "cta": "Перейти",
            "hashtags": ["crm", "partners"],
        }
    ]
}


@pytest.fixture(autouse=True)
def ai_fake():
    from app.core.config import settings

    settings.AI_PROVIDER = "fake"
    fake = get_fake_provider()
    fake.reset()
    get_fake_image_provider().reset()
    yield fake


async def _offer(client: AsyncClient, status: str = "active") -> str:
    created = await client.post(
        "/api/v1/business/offers",
        json={
            "name": "CRM Pro",
            "description": "Партнёрка CRM без гарантий дохода",
            "category": "SaaS",
            "geo": "RU",
            "conversion_type": "sale",
            "commission_type": "percent",
            "commission_value": 20,
            "status": status,
            "access_policy": "open",
            "allowed_traffic": ["telegram"],
            "forbidden_traffic": ["ppc"],
            "partner_notes": "Без гарантий",
            "product_url": "https://crmpro.example.com",
        },
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


async def _switch_partner(client: AsyncClient, name: str = "Мария") -> None:
    await become_partner(client, name)
    switch = await client.post("/api/v1/me/context", json={"role": "partner"})
    assert switch.status_code == 200


@pytest.mark.asyncio
async def test_business_manual_creative_and_publish(client: AsyncClient):
    await register_business(client, "creative-biz@example.com")
    offer_id = await _offer(client)

    created = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"type": "text", "headline": "Заголовок", "body": "Текст оффера", "cta": "Начать"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == CreativeStatus.DRAFT.value
    assert body["source"] == CreativeSource.BUSINESS.value
    assert body["partner_id"] is None
    creative_id = body["id"]

    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.status_code == 200
    assert any(item["id"] == creative_id for item in listed.json()["items"])

    published = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}/publish"
    )
    assert published.status_code == 200
    assert published.json()["status"] == CreativeStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_generate_text_structured_not_saved(
    client: AsyncClient,
    db: AsyncSession,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "creative-ai@example.com")
    offer_id = await _offer(client)
    before = await db.scalar(select(func.count(Creative.id)))
    ai_fake.queue_structured(TEXT_VARIANTS)

    response = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/generate",
        json={"type": "TEXT", "instruction": "Короткий акцент на простоту", "variants": 3},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["variants"]) == 3
    assert body["variants"][0]["headline"] == "CRM без хаоса"

    db.expire_all()
    assert await db.scalar(select(func.count(Creative.id))) == before

    usage = (
        await db.execute(select(AiUsage).where(AiUsage.generation_id == body["generation_id"]))
    ).scalar_one()
    assert usage.status == "succeeded"
    assert usage.operation == Operation.CREATIVE_TEXT_GENERATION.value
    assert usage.prompt_version == "creative-text-v2"
    assert usage.provider_metadata

    polled = await client.get(f"/api/v1/ai/generations/{body['generation_id']}")
    assert polled.status_code == 200
    assert polled.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_social_and_save_selected(
    client: AsyncClient,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "creative-social@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(SOCIAL_VARIANTS)

    generated = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/generate",
        json={"type": "social_post", "channel": "TELEGRAM", "variants": 1},
    )
    assert generated.status_code == 200, generated.text
    generation_id = generated.json()["generation_id"]

    saved = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"generation_id": generation_id, "variant_index": 0},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["status"] == "draft"
    assert body["source"] == "ai"
    assert body["type"] == CreativeType.SOCIAL_POST.value
    assert body["channel"] == "telegram"
    assert body["hashtags"] == ["crm", "partners"]


@pytest.mark.asyncio
async def test_banner_async_generation(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
):
    await register_business(client, "creative-banner@example.com")
    offer_id = await _offer(client)

    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/generate",
        json={"type": "BANNER", "format": "SQUARE_1_1", "instruction": "Минимализм"},
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "processing"
    generation_id = body["generation_id"]

    pending = await client.get(f"/api/v1/ai/generations/{generation_id}")
    assert pending.json()["status"] == "processing"

    await job_runner.run_all()
    db.expire_all()

    done = await client.get(f"/api/v1/ai/generations/{generation_id}")
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["status"] == "completed"
    assert result["variants"][0]["asset_id"]
    assert await db.scalar(select(func.count(Asset.id))) == 1

    usage = (
        await db.execute(select(AiUsage).where(AiUsage.generation_id == generation_id))
    ).scalar_one()
    assert usage.operation == Operation.CREATIVE_IMAGE_GENERATION.value
    assert usage.status == "succeeded"
    assert usage.asset_count == 1
    assert usage.image_width == 1024
    assert usage.provider_metadata

    saved = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"generation_id": generation_id, "variant_index": 0},
    )
    assert saved.status_code == 200, saved.text
    creative_id = saved.json()["id"]
    file_response = await client.get(
        f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}/file"
    )
    assert file_response.status_code == 200
    assert file_response.headers["content-type"].startswith("image/")


@pytest.mark.asyncio
async def test_banner_generation_failure(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
):
    await register_business(client, "creative-banner-fail@example.com")
    offer_id = await _offer(client)
    from app.modules.ai.errors import ai_timeout

    get_fake_image_provider().fail_with(ai_timeout())
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/generate",
        json={"type": "banner", "format": "portrait_4_5"},
    )
    assert started.status_code == 200
    generation_id = started.json()["generation_id"]
    await job_runner.run_all()

    failed = await client.get(f"/api/v1/ai/generations/{generation_id}")
    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["code"] == "AI_TIMEOUT"
    usage = (
        await db.execute(select(AiUsage).where(AiUsage.generation_id == generation_id))
    ).scalar_one()
    assert usage.status == "failed"
    assert usage.error_code == "AI_TIMEOUT"


@pytest.mark.asyncio
async def test_partner_private_creative_visibility(client: AsyncClient):
    await register_business(client, "creative-vis-biz@example.com")
    offer_id = await _offer(client)
    await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"type": "text", "headline": "Черновик", "body": "Не для партнёров", "cta": "X"},
    )
    published = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"type": "text", "headline": "Для партнёров", "body": "Можно использовать", "cta": "Копировать"},
    )
    pub_id = published.json()["id"]
    await client.post(f"/api/v1/business/offers/{offer_id}/creatives/{pub_id}/publish")

    await _switch_partner(client, "Партнёр А")
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200, join.text

    mine = await client.post(
        f"/api/v1/partner/offers/{offer_id}/creatives",
        json={"type": "text", "headline": "Мой пост", "body": "Приватный", "cta": "Перейти"},
    )
    assert mine.status_code == 200, mine.text
    private_id = mine.json()["id"]
    assert mine.json()["partner_id"]
    assert mine.json()["status"] == "active"

    listed = await client.get(f"/api/v1/partner/offers/{offer_id}/creatives")
    ids = {item["id"] for item in listed.json()["items"]}
    assert pub_id in ids
    assert private_id in ids
    assert all(item["headline"] != "Черновик" for item in listed.json()["items"])

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await register_user(other, "partner-b@example.com")
        await become_partner(other, "Партнёр Б")
        await other.post("/api/v1/me/context", json={"role": "partner"})
        await other.post(f"/api/v1/partner/offers/{offer_id}/join")
        other_list = await other.get(f"/api/v1/partner/offers/{offer_id}/creatives")
        other_ids = {item["id"] for item in other_list.json()["items"]}
        assert private_id not in other_ids
        assert pub_id in other_ids
        stolen = await other.patch(
            f"/api/v1/partner/offers/{offer_id}/creatives/{private_id}",
            json={"body": "взлом"},
        )
        assert stolen.status_code in {403, 404}


@pytest.mark.asyncio
async def test_business_cannot_use_foreign_offer(client: AsyncClient):
    await register_business(client, "owner@example.com")
    offer_id = await _offer(client)
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await register_business(other, "intruder@example.com")
        response = await other.get(f"/api/v1/business/offers/{offer_id}/creatives")
        assert response.status_code == 404
        generated = await other.post(
            f"/api/v1/business/offers/{offer_id}/creatives/generate",
            json={"type": "text"},
        )
        assert generated.status_code == 404


@pytest.mark.asyncio
async def test_partner_cannot_generate_without_access(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "locked-biz@example.com")
    offer_id = await _offer(client, status="draft")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await register_user(other, "locked-partner@example.com")
        await become_partner(other, "Нет доступа")
        await other.post("/api/v1/me/context", json={"role": "partner"})
        ai_fake.queue_structured(TEXT_VARIANTS)
        response = await other.post(
            f"/api/v1/partner/offers/{offer_id}/creatives/generate",
            json={"type": "text"},
        )
        assert response.status_code in {403, 404}


@pytest.mark.asyncio
async def test_rewrite_does_not_mutate_until_patch(
    client: AsyncClient,
    db: AsyncSession,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "rewrite-biz@example.com")
    offer_id = await _offer(client)
    created = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={"type": "text", "headline": "Старый", "body": "Длинный рекламный текст", "cta": "Купить"},
    )
    creative_id = created.json()["id"]
    ai_fake.queue_structured(
        {"headline": "Короткий", "body": "Спокойный текст", "cta": "Смотреть", "hashtags": []}
    )
    rewritten = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}/rewrite",
        json={"instruction": "Сделай короче и менее рекламным"},
    )
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["proposed"]["headline"] == "Короткий"
    detail = (await db.execute(select(Creative).where(Creative.id == creative_id))).scalar_one()
    assert detail.text_content["headline"] == "Старый"

    patched = await client.patch(
        f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}",
        json={"headline": "Короткий", "body": "Спокойный текст", "cta": "Смотреть"},
    )
    assert patched.status_code == 200
    assert patched.json()["headline"] == "Короткий"


@pytest.mark.asyncio
async def test_policy_blocks_forbidden_claim(client: AsyncClient, db: AsyncSession):
    await register_business(client, "policy-biz@example.com")
    offer_id = await _offer(client)
    offer = (await db.execute(select(Offer).where(Offer.id == int(offer_id)))).scalar_one()
    db.add(
        BrandKit(
            business_id=offer.business_id,
            forbidden_claims=["гарантированный доход"],
            mandatory_disclaimers=["не является офертой"],
        )
    )
    await db.commit()

    blocked = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives",
        json={
            "type": "text",
            "headline": "Заработок",
            "body": "Гарантированный доход каждому",
            "cta": "Жми",
        },
    )
    assert blocked.status_code == 200
    creative_id = blocked.json()["id"]
    assert blocked.json()["policy_status"] == "blocked"
    published = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}/publish"
    )
    assert published.status_code == 400
    assert published.json()["error"]["code"] == "CREATIVE_CONTENT_BLOCKED"


def test_policy_validator_disclaimer_and_rqcid():
    validator = CreativePolicyValidator()
    offer = Offer(
        business_id=1,
        name="X",
        description="desc",
        partner_notes="",
        forbidden_traffic=[],
    )
    kit = BrandKit(business_id=1, mandatory_disclaimers=["есть риски"], forbidden_claims=[])
    result = validator.validate_text(
        {"headline": "A", "body": "rqcid abc", "cta": "Go"},
        offer=offer,
        brand_kit=kit,
    )
    assert result["status"] == "blocked"
    codes = {item["code"] for item in result["issues"]}
    assert "TRACKING_ID_FORBIDDEN" in codes
    assert "DISCLAIMER_MISSING" in codes


def test_promotion_context_omits_ids_and_includes_brand():
    offer = Offer(
        id=99,
        business_id=1,
        name="CRM Pro",
        description="Описание продукта",
        category="SaaS",
        geo="RU",
        partner_notes="Без бренда",
        allowed_traffic=["telegram"],
        forbidden_traffic=["ppc"],
        commission_rules=[],
    )
    kit = BrandKit(
        business_id=1,
        tone_of_voice="спокойный",
        brand_colors=["#27503A"],
        allowed_claims=["удобный интерфейс"],
        forbidden_claims=["гарантия прибыли"],
        mandatory_disclaimers=["не является офертой"],
    )
    payload = OfferPromotionContextBuilder().from_offer(offer, brand_kit=kit, channel="telegram")
    dumped = str(payload)
    assert payload["purpose"] == "CUSTOMER_ACQUISITION"
    assert payload["targetAudienceRole"] == "END_CUSTOMER"
    assert payload["promotedObject"] == "PRODUCT_OR_SERVICE"
    assert payload["constraints"]["do_not_generate_rqcid"] is True
    assert payload["constraints"]["do_not_advertise_affiliate_program"] is True
    assert "password" not in dumped
    assert payload["brand"]["tone_of_voice"] == "спокойный"
    assert "ppc" not in payload["restrictions"]
    assert payload["affiliateConstraints"]["forbiddenTraffic"] == ["ppc"]
    assert payload["affiliateConstraints"]["partnerNotes"] == "Без бренда"
    assert payload["productContext"]["name"] == "CRM Pro"
    assert payload["offer"]["name"] == "CRM Pro"
    assert payload["offer"].get("id") is None
    assert "partner_notes" not in payload["offer"]
    assert "commission_value" not in dumped
    assert "commission_type" not in dumped

