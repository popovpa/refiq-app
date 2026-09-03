from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CreativeChannel, CreativeSource, CreativeStatus, CreativeType
from app.main import app as fastapi_app
from app.modules.ai.capabilities import Operation
from app.modules.ai.errors import AiError
from app.modules.ai.jobs import DeferredJobRunner
from app.modules.ai.providers.fake import FakeTextGenerationProvider
from app.modules.ai.resolver import get_fake_image_provider, get_fake_provider
from app.modules.ai.usage.models import AiUsage
from app.modules.assets.models import Asset
from app.modules.creatives.models import Creative
from tests.helpers import become_partner, register_business

BRIEF = {
    "targetAudience": "Команды продаж в RU",
    "mainValueProposition": "CRM без хаоса в сделках",
    "keyBenefits": ["Учёт сделок", "Аналитика", "Единый кабинет"],
    "toneOfVoice": "спокойный экспертный",
    "cta": "Узнать больше",
    "restrictions": ["Не обещать гарантию результата"],
    "creativeConcepts": ["спокойный офисный интерфейс", "команда за ноутбуками"],
}

KIT_TEXTS = {
    "universal_ad": {
        "headline": "CRM без таблиц",
        "body": "Ведите сделки и аналитику в одном кабинете.",
        "cta": "Узнать больше",
    },
    "short_ad": {
        "headline": "Сделки без хаоса",
        "body": "Единый кабинет для команды продаж.",
        "cta": "Попробовать",
    },
    "headlines": [
        "CRM для продаж",
        "Сделки без таблиц",
        "Аналитика под контролем",
        "Кабинет в одном месте",
        "Простая CRM",
    ],
    "descriptions": [
        "Кабинет сделок и аналитики.",
        "Учёт сделок без лишних таблиц.",
        "Инструмент для команды продаж.",
    ],
    "telegram_posts": [
        {
            "headline": "Telegram: CRM Pro",
            "body": "Ведите сделки без хаоса в таблицах.",
            "cta": "Открыть",
            "hashtags": ["crm", "sales"],
        },
        {
            "headline": "Пост 2",
            "body": "Аналитика воронки в одном кабинете.",
            "cta": "Смотреть",
            "hashtags": ["saas"],
        },
        {
            "headline": "Пост 3",
            "body": "Запустите учёт сделок за один день.",
            "cta": "Начать",
            "hashtags": [],
        },
    ],
    "vk_posts": [
        {
            "headline": "VK: CRM Pro",
            "body": "Сделки, задачи и отчёты в одном месте.",
            "cta": "Подробнее",
            "hashtags": ["crm"],
        },
        {
            "headline": "VK 2",
            "body": "Кабинет без обещаний чуда.",
            "cta": "Открыть",
            "hashtags": [],
        },
        {
            "headline": "VK 3",
            "body": "Понятный интерфейс для отдела продаж.",
            "cta": "Смотреть",
            "hashtags": [],
        },
    ],
}

SINGLE_TEXT = {
    "headline": "Новый Telegram пост",
    "body": "Обновлённый текст только для этого материала.",
    "cta": "Перейти",
    "hashtags": ["crm"],
    "items": [],
}

META = {
    "primaryTexts": [
        "CRM для команды, которой нужен порядок в сделках.",
        "Ведите воронку без таблиц и хаоса.",
        "Кабинет сделок и аналитики в одном месте.",
    ],
    "headlines": [
        "CRM для продаж",
        "Сделки без таблиц",
        "Аналитика под контролем",
        "Кабинет сделок",
        "CRM без хаоса",
    ],
    "descriptions": [
        "Кабинет сделок и отчётов.",
        "Учёт сделок без лишних таблиц.",
        "Инструмент для отдела продаж.",
    ],
}

GOOGLE = {
    "headlines": ["CRM для продаж", "Сделки без таблиц", "Аналитика", "Кабинет сделок", "CRM без хаоса"],
    "descriptions": [
        "Кабинет сделок и отчётов для команды.",
        "Учёт сделок без лишних таблиц.",
        "Запустите учёт за один день.",
        "Понятный интерфейс для продаж.",
    ],
}

TIKTOK = {
    "hooks": ["Сделки без таблиц", "Воронка в одном кабинете", "CRM без хаоса"],
    "captions": [
        "Ведите сделки и аналитику в одном месте.",
        "Кабинет для команды продаж без лишнего шума.",
        "Запустите учёт за один день.",
    ],
    "ctas": ["Узнать больше", "Открыть кабинет", "Попробовать"],
}

YANDEX = {
    "headlines": [
        "CRM для продаж",
        "Сделки без таблиц",
        "Аналитика под контролем",
        "Кабинет сделок",
        "CRM без хаоса",
    ],
    "descriptions": [
        "Кабинет сделок и отчётов.",
        "Учёт сделок без лишних таблиц.",
        "Инструмент для отдела продаж.",
        "Запустите учёт за один день.",
        "Понятный интерфейс для команды.",
    ],
}


def _copy(block: dict) -> dict:
    return {**block, "hashtags": [], "items": []}


def _lines(items: list[str]) -> dict:
    return {"headline": items[0], "body": "\n".join(items), "cta": "", "hashtags": [], "items": items}


@pytest.fixture(autouse=True)
def ai_fake():
    from app.core.config import settings

    previous = (
        settings.AI_PROVIDER,
        settings.AI_TEXT_PROVIDER,
        settings.AI_IMAGE_PROVIDER,
    )
    settings.AI_PROVIDER = "fake"
    settings.AI_TEXT_PROVIDER = "fake"
    settings.AI_IMAGE_PROVIDER = "fake"
    fake = get_fake_provider()
    fake.reset()
    get_fake_image_provider().reset()
    yield fake
    settings.AI_PROVIDER, settings.AI_TEXT_PROVIDER, settings.AI_IMAGE_PROVIDER = previous


async def _offer(client: AsyncClient) -> str:
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
            "status": "active",
            "access_policy": "open",
            "allowed_traffic": ["telegram"],
            "forbidden_traffic": ["ppc"],
            "partner_notes": "Без гарантий",
            "product_url": "https://crmpro.example.com",
        },
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


IMAGE_SPEC = {
    "concept": "product_hero",
    "format": "1:1",
    "subject": "CRM Pro",
    "audience": "команды продаж",
    "visualDirection": "спокойный офисный интерфейс",
    "headline": "CRM Pro",
    "cta": "Узнать больше",
    "imagePrompt": (
        "Рекламный баннер продукта CRM Pro для конечного покупателя. "
        "Ноутбук с кабинетом сделок на современном столе, коммерческая фотография. "
        "Только текст «CRM Pro» и «Узнать больше». Без QR и без лишних надписей."
    ),
}


def _queue_kit(ai_fake: FakeTextGenerationProvider) -> None:
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured({"posts": KIT_TEXTS["telegram_posts"]})
    ai_fake.queue_structured(META)
    ai_fake.queue_structured(GOOGLE)
    ai_fake.queue_structured(YANDEX)
    ai_fake.queue_structured({"posts": KIT_TEXTS["vk_posts"]})
    ai_fake.queue_structured(TIKTOK)
    ai_fake.queue_structured(IMAGE_SPEC)
    ai_fake.queue_structured(IMAGE_SPEC)


def _promo_png(size: int = 256) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (size, size), (24, 86, 168)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _offer_link(client: AsyncClient, offer_id: str, name: str = "QR") -> dict:
    await become_partner(client, f"{name} Partner")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200, join.text
    created = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": int(offer_id), "name": name, "traffic_source": "telegram"},
    )
    assert created.status_code == 200, created.text
    await client.post("/api/v1/me/context", json={"role": "business"})
    return created.json()


@pytest.mark.asyncio
async def test_promo_kit_creates_drafts_and_usage(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
    monkeypatch,
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OPENAI_MODEL", "offer-model")
    monkeypatch.setattr(settings, "OPENAI_PROMO_MODEL", "promo-luna-test")
    monkeypatch.setattr(settings, "OPENAI_PROMO_REASONING_EFFORT", "none")

    await register_business(client, "promo-kit@example.com")
    offer_id = await _offer(client)
    _queue_kit(ai_fake)

    started = await client.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
    assert started.status_code == 202, started.text
    body = started.json()
    assert body["status"] == "queued"
    run_id = body["run_id"]

    await job_runner.run_all()
    db.expire_all()

    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["status"] == "completed"
    assert result["total_items"] == 7
    assert len(result["created_ids"]) == 8
    assert result["errors"] == []
    assert all(item["status"] == "completed" for item in result["items"])

    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    items = listed.json()["items"]
    assert len(items) == 8
    assert all(item["status"] == CreativeStatus.DRAFT.value for item in items)
    assert all(item["source"] == CreativeSource.AI.value for item in items)
    assert {item["type"] for item in items} == {
        CreativeType.TEXT.value,
        CreativeType.SOCIAL_POST.value,
        CreativeType.BANNER.value,
    }
    assert any(item["channel"] == CreativeChannel.TELEGRAM.value for item in items)
    assert any(item["channel"] == CreativeChannel.VK.value for item in items)
    assert any(item["channel"] == CreativeChannel.YANDEX_DIRECT.value for item in items)
    assert any(item["channel"] == CreativeChannel.META_ADS.value for item in items)
    assert any(item["channel"] == CreativeChannel.GOOGLE_ADS.value for item in items)
    assert any(item["channel"] == CreativeChannel.TIKTOK_ADS.value for item in items)
    yandex = next(item for item in items if item["channel"] == CreativeChannel.YANDEX_DIRECT.value)
    assert len(yandex["items"]) == 5
    assert len(yandex["descriptions"]) == 5
    telegram = next(item for item in items if item["channel"] == CreativeChannel.TELEGRAM.value)
    assert len(telegram["variants"]) == 3
    assert telegram["variants"][0]["headline"] == "Telegram: CRM Pro"

    banners = [item for item in items if item["type"] == CreativeType.BANNER.value]
    assert len(banners) == 2
    for banner in banners:
        assert banner["format"] == "square_1_1"
        file_response = await client.get(
            f"/api/v1/business/offers/{offer_id}/promo-materials/{banner['id']}/image"
        )
        assert file_response.status_code == 200
        assert file_response.headers["content-type"].startswith("image/")
        one = await client.get(f"/api/v1/business/offers/{offer_id}/creatives/{banner['id']}")
        assert one.status_code == 200
        assert one.json()["id"] == banner["id"]

    assets = list((await db.execute(select(Asset))).scalars().all())
    assert len(assets) == 2
    for asset in assets:
        assert asset.storage_key.startswith(f"offers-promo/{offer_id}/")
        assert asset.storage_key.endswith(".png")

    usages = list((await db.execute(select(AiUsage))).scalars().all())
    operations = {item.operation for item in usages}
    assert Operation.PROMO_BRIEF_GENERATE.value in operations
    assert Operation.PROMO_TEXT_GENERATE.value in operations
    assert Operation.PROMO_YANDEX_GENERATE.value in operations
    assert Operation.PROMO_IMAGE_GENERATE.value in operations
    assert Operation.PROMO_IMAGE_PROMPT_GENERATE.value in operations
    assert all(call.model == "promo-luna-test" for call in ai_fake.calls)
    assert all((call.reasoning_effort or "none") == "none" for call in ai_fake.calls)
    from app.modules.creatives.promo_runs import OfferPromoGenerationRun

    stored = await db.get(OfferPromoGenerationRun, run_id)
    assert stored is not None
    assert stored.offer_snapshot
    assert stored.promotion_brief
    assert stored.offer_snapshot["purpose"] == "CUSTOMER_ACQUISITION"
    assert stored.offer_snapshot["promotedObject"] == "PRODUCT_OR_SERVICE"
    assert stored.offer_snapshot["targetAudienceRole"] == "END_CUSTOMER"
    assert "productContext" in stored.offer_snapshot
    assert "partner_notes" not in stored.offer_snapshot["offer"]
    assert "allowed_traffic" not in stored.offer_snapshot["offer"]
    assert stored.offer_snapshot["affiliateConstraints"]["mustNotAppearInCustomerCreative"] is True
    dumped = str(stored.offer_snapshot)
    assert "commission_value" not in dumped
    assert "commission_type" not in dumped
    image_prompts = [call.prompt for call in get_fake_image_provider().calls]
    assert image_prompts
    for prompt in image_prompts:
        lower = prompt.lower()
        assert "crm pro" in lower
        assert IMAGE_SPEC["imagePrompt"] in prompt
        assert "Описание оффера (обязательно отразить в сцене):" in prompt
        assert "комиссия" not in lower
        assert "партнёрская программа" not in lower
        assert "allowed_traffic" not in lower
        assert "partner_notes" not in lower
        assert "50000" not in prompt
        assert "commission" not in lower
    brief_usages = [item for item in usages if item.operation == Operation.PROMO_BRIEF_GENERATE.value]
    assert len(brief_usages) == 1
    assert brief_usages[0].provider_metadata["generation_run_id"] == run_id
    assert brief_usages[0].provider_metadata["offer_id"] == int(offer_id)


@pytest.mark.asyncio
async def test_partner_sees_only_published_promo_materials(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-pub@example.com")
    offer_id = await _offer(client)
    _queue_kit(ai_fake)
    started = await client.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    created_ids = done.json()["created_ids"]
    text_id = created_ids[0]
    image_id = created_ids[-1]

    await client.post(f"/api/v1/business/offers/{offer_id}/creatives/{text_id}/publish")

    await become_partner(client, "Мария")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    join = await client.post(f"/api/v1/partner/offers/{offer_id}/join")
    assert join.status_code == 200, join.text

    listed = await client.get(f"/api/v1/partner/offers/{offer_id}/creatives")
    ids = {item["id"] for item in listed.json()["items"]}
    assert text_id in ids
    assert image_id not in ids

    draft = await client.get(f"/api/v1/partner/offers/{offer_id}/creatives/{image_id}")
    assert draft.status_code == 404
    draft_file = await client.get(
        f"/api/v1/partner/offers/{offer_id}/promo-materials/{image_id}/image"
    )
    assert draft_file.status_code == 404

    await client.post("/api/v1/me/context", json={"role": "business"})
    await client.post(f"/api/v1/business/offers/{offer_id}/creatives/{image_id}/publish")
    await client.post("/api/v1/me/context", json={"role": "partner"})
    image = await client.get(
        f"/api/v1/partner/offers/{offer_id}/promo-materials/{image_id}/image"
    )
    assert image.status_code == 200


@pytest.mark.asyncio
async def test_regenerate_updates_only_one_material(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-regen@example.com")
    offer_id = await _offer(client)
    _queue_kit(ai_fake)
    started = await client.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
    await job_runner.run_all()
    items = (await client.get(f"/api/v1/business/offers/{offer_id}/creatives")).json()["items"]
    telegram = next(item for item in items if item["channel"] == "telegram")
    banner = next(item for item in items if item["type"] == "banner")
    old_asset_id = banner["asset_id"]
    old_body = telegram["body"]

    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(
        {
            "posts": [
                {
                    "headline": SINGLE_TEXT["headline"],
                    "body": SINGLE_TEXT["body"],
                    "cta": SINGLE_TEXT["cta"],
                    "hashtags": SINGLE_TEXT["hashtags"],
                }
            ]
        }
    )
    regenerated = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{telegram['id']}/regenerate"
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["id"] == telegram["id"]
    assert regenerated.json()["body"] != old_body
    assert regenerated.json()["headline"] == SINGLE_TEXT["headline"]

    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert len(listed.json()["items"]) == 8

    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(IMAGE_SPEC)
    image = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{banner['id']}/regenerate"
    )
    assert image.status_code == 200, image.text
    db.expire_all()
    assert image.json()["asset_id"] != old_asset_id
    assert await db.scalar(select(Asset.id).where(Asset.id == old_asset_id)) is None
    new_asset = (
        await db.execute(select(Asset).where(Asset.id == image.json()["asset_id"]))
    ).scalar_one()
    assert new_asset.storage_key.startswith(f"offers-promo/{offer_id}/{banner['id']}-")

    patched = await client.patch(
        f"/api/v1/business/offers/{offer_id}/creatives/{telegram['id']}",
        json={"body": "Ручная правка текста", "cta": "Открыть"},
    )
    assert patched.status_code == 200
    assert patched.json()["body"] == "Ручная правка текста"

    unpublished = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/{telegram['id']}/unpublish"
    )
    assert unpublished.json()["status"] == CreativeStatus.DRAFT.value

    deleted = await client.delete(
        f"/api/v1/business/offers/{offer_id}/creatives/{banner['id']}"
    )
    assert deleted.status_code == 200
    remaining = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert all(item["id"] != banner["id"] for item in remaining.json()["items"])


@pytest.mark.asyncio
async def test_partial_kit_keeps_successful_materials(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-partial@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(BRIEF)
    for _ in range(6):
        ai_fake.queue_structured({"unexpected": True})
    ai_fake.queue_structured(IMAGE_SPEC)
    ai_fake.queue_structured(IMAGE_SPEC)

    started = await client.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
    await job_runner.run_all()
    done = await client.get(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{started.json()['run_id']}"
    )
    body = done.json()
    assert body["status"] == "completed_with_errors"
    assert body["created_ids"]
    assert body["failed_items"] == 6
    assert body["completed_items"] == 1

    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    items = listed.json()["items"]
    assert items
    assert all(item["type"] == CreativeType.BANNER.value for item in items)


@pytest.mark.asyncio
async def test_foreign_business_cannot_generate_promo_kit(
    client: AsyncClient,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-owner@example.com")
    offer_id = await _offer(client)
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await register_business(other, "promo-intruder@example.com")
        _queue_kit(ai_fake)
        response = await other.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
        assert response.status_code == 404
        listed = await other.get(f"/api/v1/business/offers/{offer_id}/creatives")
        assert listed.status_code == 404
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_selectable_slots_skip_vk_add_qr(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-slots@example.com")
    offer_id = await _offer(client)
    catalog = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-catalog")
    assert catalog.status_code == 200
    ids = {item["id"] for item in catalog.json()["items"]}
    assert ids == {
        "telegram",
        "meta_ads",
        "google_ads",
        "yandex_direct",
        "vk_ads",
        "tiktok_ads",
        "images_1_1",
        "images_16_9",
        "images_9_16",
        "images_qr",
    }
    assert "universal_ad" not in ids
    labels = {item["id"]: item["label"] for item in catalog.json()["items"]}
    assert labels["meta_ads"] == "Meta Ads (Facebook)"
    assert labels["vk_ads"] == "VK Реклама"

    link = await _offer_link(client, offer_id)
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured({"posts": KIT_TEXTS["telegram_posts"]})
    ai_fake.queue_structured(YANDEX)
    ai_fake.queue_structured(IMAGE_SPEC)

    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={
            "slots": ["telegram", "yandex_direct", "images_qr"],
            "qr_tracking_link_id": link["id"],
        },
    )
    assert started.status_code == 202, started.text
    await job_runner.run_all()
    done = await client.get(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{started.json()['run_id']}"
    )
    body = done.json()
    assert body["status"] == "completed"
    assert [item["material_type"] for item in body["items"]] == [
        "telegram",
        "yandex_direct",
        "images_qr",
    ]
    listed = (await client.get(f"/api/v1/business/offers/{offer_id}/creatives")).json()["items"]
    assert not any(item["channel"] == "vk" for item in listed)
    assert any(item["channel"] == "yandex_direct" for item in listed)
    qr = next(item for item in listed if item["selected_variant"] == "images_qr")
    assert qr["format"] == "square_1_1"


@pytest.mark.asyncio
async def test_qr_slot_requires_tracking_link(
    client: AsyncClient,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-qr-required@example.com")
    offer_id = await _offer(client)
    missing = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["images_qr"]},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "PROMO_QR_LINK_REQUIRED"
    foreign = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["images_qr"], "qr_tracking_link_id": 999999},
    )
    assert foreign.status_code == 400
    assert foreign.json()["error"]["code"] == "PROMO_QR_LINK_INVALID"
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_cancel_before_worker_cancels_queued_items(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-cancel@example.com")
    offer_id = await _offer(client)
    _queue_kit(ai_fake)
    started = await client.post(f"/api/v1/business/offers/{offer_id}/creatives/promo-kit")
    run_id = started.json()["run_id"]
    cancelled = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/cancel"
    )
    assert cancelled.status_code == 200, cancelled.text
    await job_runner.run_all()
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    body = done.json()
    assert body["status"] == "cancelled"
    assert body["cancel_requested"] is True
    assert all(item["status"] == "cancelled" for item in body["items"])
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"] == []


@pytest.mark.asyncio
async def test_brief_failure_marks_run_and_items_failed(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-brief-fail@example.com")
    offer_id = await _offer(client)
    ai_fake.fail_with(AiError("AI_UNAUTHORIZED", "AI provider rejected the request", 502))
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    assert started.status_code == 202, started.text
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    body = done.json()
    assert body["status"] == "failed"
    assert body["failed_items"] == body["total_items"]
    assert body["items"]
    assert all(item["status"] == "failed" for item in body["items"])
    assert all(item["error_code"] == "AI_UNAUTHORIZED" for item in body["items"])
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"] == []
    active = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/active")
    assert active.json()["run"]["status"] == "failed"


@pytest.mark.asyncio
async def test_brief_failure_can_be_retried(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-brief-retry@example.com")
    offer_id = await _offer(client)
    ai_fake.fail_with(AiError("AI_UNAVAILABLE", "AI provider is temporarily unavailable", 503))
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    assert started.status_code == 202, started.text
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    failed = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    item_id = failed.json()["items"][0]["id"]
    ai_fake.reset()
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    retried = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/items/{item_id}/retry"
    )
    assert retried.status_code == 200, retried.text
    await job_runner.run_all()
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    assert done.json()["status"] == "completed"
    assert done.json()["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_running_run_then_retry(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-cancel-running@example.com")
    offer_id = await _offer(client)
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    run_id = started.json()["run_id"]
    from app.modules.creatives.promo_runs import OfferPromoGenerationRun

    run = await db.get(OfferPromoGenerationRun, run_id)
    assert run is not None
    run.status = "running"
    await db.commit()
    cancelled = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/cancel"
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert all(item["status"] == "cancelled" for item in cancelled.json()["items"])
    item_id = cancelled.json()["items"][0]["id"]
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    retried = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/items/{item_id}/retry"
    )
    assert retried.status_code == 200, retried.text
    await job_runner.run_all()
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    assert done.json()["status"] == "completed"
    assert done.json()["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_then_start_new_kit(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-restart@example.com")
    offer_id = await _offer(client)
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    run_id = started.json()["run_id"]
    cancelled = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/cancel"
    )
    assert cancelled.status_code == 200, cancelled.text
    await job_runner.run_all()
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["short_ad"]))
    restarted = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["short_ad"]},
    )
    assert restarted.status_code == 202, restarted.text
    assert restarted.json()["run_id"] != run_id
    await job_runner.run_all()
    done = await client.get(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{restarted.json()['run_id']}"
    )
    assert done.json()["status"] == "completed"
    assert done.json()["items"][0]["material_type"] == "short_ad"


@pytest.mark.asyncio
async def test_retry_cancelled_item(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-retry-cancel@example.com")
    offer_id = await _offer(client)
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    run_id = started.json()["run_id"]
    cancelled = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/cancel"
    )
    assert cancelled.status_code == 200, cancelled.text
    await job_runner.run_all()
    item_id = cancelled.json()["items"][0]["id"]
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    retried = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/items/{item_id}/retry"
    )
    assert retried.status_code == 200, retried.text
    await job_runner.run_all()
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    assert done.json()["status"] == "completed"
    assert done.json()["items"][0]["status"] == "completed"
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"]


@pytest.mark.asyncio
async def test_active_run_survives_and_can_retry_failed(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-retry@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured({"unexpected": True})

    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    active = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/active")
    assert active.json()["run"]["id"] == run_id
    assert active.json()["run"]["status"] == "completed_with_errors"
    item_id = active.json()["run"]["items"][0]["id"]

    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    retried = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/items/{item_id}/retry"
    )
    assert retried.status_code == 200, retried.text
    await job_runner.run_all()
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    assert done.json()["status"] == "completed"
    assert done.json()["items"][0]["status"] == "completed"
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"]


@pytest.mark.asyncio
async def test_delete_generated_text_material(
    client: AsyncClient,
    db: AsyncSession,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-delete-text@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    done = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}")
    creative_id = done.json()["created_ids"][0]
    deleted = await client.delete(f"/api/v1/business/offers/{offer_id}/creatives/{creative_id}")
    assert deleted.status_code == 200, deleted.text
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"] == []
    from app.modules.creatives.promo_runs import OfferPromoGenerationItem

    db.expire_all()
    item = (
        await db.execute(
            select(OfferPromoGenerationItem).where(
                OfferPromoGenerationItem.id == done.json()["items"][0]["id"]
            )
        )
    ).scalar_one()
    assert item.promo_material_id is None
    assert creative_id not in ((item.result or {}).get("creative_ids") or [])


@pytest.mark.asyncio
async def test_ack_after_completed_run_returns_payload(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-ack@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(_copy(KIT_TEXTS["universal_ad"]))
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["universal_ad"]},
    )
    await job_runner.run_all()
    run_id = started.json()["run_id"]
    acked = await client.post(
        f"/api/v1/business/offers/{offer_id}/promo-generation-runs/{run_id}/ack"
    )
    assert acked.status_code == 200, acked.text
    body = acked.json()
    assert body["id"] == run_id
    assert body["status"] == "completed"
    assert body["updated_at"]
    active = await client.get(f"/api/v1/business/offers/{offer_id}/promo-generation-runs/active")
    assert active.json()["run"] is None
    listed = await client.get(f"/api/v1/business/offers/{offer_id}/creatives")
    assert listed.json()["items"]


@pytest.mark.asyncio
async def test_partner_qr_image_uses_tracking_link(
    client: AsyncClient,
    job_runner: DeferredJobRunner,
    ai_fake: FakeTextGenerationProvider,
):
    await register_business(client, "promo-qr@example.com")
    offer_id = await _offer(client)
    ai_fake.queue_structured(BRIEF)
    ai_fake.queue_structured(IMAGE_SPEC)
    get_fake_image_provider().queue_image(_promo_png())
    link = await _offer_link(client, offer_id)
    started = await client.post(
        f"/api/v1/business/offers/{offer_id}/creatives/promo-kit",
        json={"slots": ["images_qr"], "qr_tracking_link_id": link["id"]},
    )
    await job_runner.run_all()
    listed = (await client.get(f"/api/v1/business/offers/{offer_id}/creatives")).json()["items"]
    qr = listed[0]
    await client.post(f"/api/v1/business/offers/{offer_id}/creatives/{qr['id']}/publish")
    business_file = await client.get(
        f"/api/v1/business/offers/{offer_id}/promo-materials/{qr['id']}/image"
    )
    assert business_file.status_code == 200
    base_bytes = business_file.content

    await client.post("/api/v1/me/context", json={"role": "partner"})
    second = await client.post(
        "/api/v1/partner/links",
        json={"offer_id": int(offer_id), "name": "QR-2", "traffic_source": "telegram"},
    )
    assert second.status_code == 200, second.text
    partner_file = await client.get(
        f"/api/v1/partner/offers/{offer_id}/promo-materials/{qr['id']}/image"
    )
    assert partner_file.status_code == 200
    assert partner_file.content != base_bytes
    assert len(partner_file.content) > len(base_bytes) or partner_file.content != base_bytes
