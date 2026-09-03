import ast
from pathlib import Path

import pytest
import httpx
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.ai.capabilities import Capability, Operation
from app.modules.ai.errors import ai_timeout, is_retryable_provider_error, map_provider_http_error
from app.modules.ai.providers.fake import FakeTextGenerationProvider
from app.modules.ai.providers.openai_text import OpenAITextGenerationProvider
from app.modules.ai.generation import ImageGenerationRequest, StructuredGenerationRequest
from app.modules.ai.resolver import ProviderResolver, get_fake_image_provider, get_fake_provider
from app.modules.ai.usage.models import AiUsage
from app.modules.offers.models import Offer
from tests.helpers import register_business

AI_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "ai"

DRAFT_PAYLOAD = {
    "draft": {
        "name": "English for IT",
        "description": "Онлайн-курс английского для IT-специалистов.",
        "category": "Education",
        "geo": "RU",
        "partner_notes": "Можно Telegram и контент.",
        "allowed_traffic": ["telegram", "content"],
        "forbidden_traffic": ["ppc"],
        "product_url": "https://example.com/course",
    },
    "recommendations": {
        "conversion_type": "sale",
        "commission_type": "percent",
        "commission_value": 15,
        "commission_currency": "RUB",
        "attribution_window_days": 30,
        "access_policy": "open",
    },
}


@pytest.fixture(autouse=True)
def ai_fake(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    fake = get_fake_provider()
    fake.reset()
    get_fake_image_provider().reset()
    yield fake


@pytest.fixture(autouse=True)
def stub_website(monkeypatch):
    calls: list[str] = []

    async def fake(url: str):
        calls.append(url)
        from app.modules.ai.website.models import WebsiteContext

        return WebsiteContext.unavailable(url, "stub")

    fake.calls = calls
    monkeypatch.setattr(
        "app.modules.ai.application.offer.generate_offer_draft.load_website_context",
        fake,
    )
    return fake


def test_application_layer_does_not_import_openai():
    blocked = ("openai", "httpx")
    blocked_modules = ("app.modules.ai.providers.openai_text",)
    roots = [
        AI_ROOT / "application",
        AI_ROOT / "context",
        AI_ROOT / "prompts",
        AI_ROOT / "dto.py",
        AI_ROOT / "schemas.py",
        AI_ROOT / "offer_fields.py",
        AI_ROOT / "generation.py",
        AI_ROOT / "capabilities.py",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        else:
            files.extend(root.rglob("*.py"))
    for path in files:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in blocked, path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in blocked_modules, path
                assert node.module.split(".")[0] not in blocked, path


def test_provider_resolver_uses_configured_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    assert isinstance(ProviderResolver().text(Capability.STRUCTURED_GENERATION), FakeTextGenerationProvider)
    assert isinstance(ProviderResolver().image(Capability.IMAGE_GENERATION), type(get_fake_image_provider()))
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    assert isinstance(ProviderResolver().text(Capability.TEXT_GENERATION), OpenAITextGenerationProvider)
    from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider

    assert isinstance(ProviderResolver().image(Capability.IMAGE_GENERATION), OpenAIImageGenerationProvider)
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "yandex")
    from app.modules.ai.providers.deepseek_text import DeepSeekTextGenerationProvider
    from app.modules.ai.providers.yandex_alice_art import YandexAliceArtImageProvider

    assert isinstance(ProviderResolver().text(Capability.STRUCTURED_GENERATION), DeepSeekTextGenerationProvider)
    assert isinstance(ProviderResolver().image(Capability.IMAGE_GENERATION), YandexAliceArtImageProvider)
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    with pytest.raises(Exception) as exc:
        ProviderResolver().text(Capability.IMAGE_GENERATION)
    assert exc.value.code == "AI_CAPABILITY_UNAVAILABLE"
    with pytest.raises(Exception) as exc:
        ProviderResolver().image(Capability.IMAGE_EDIT)
    assert exc.value.code == "AI_CAPABILITY_UNAVAILABLE"


def test_resolver_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_PROVIDER", "gigachat")
    with pytest.raises(Exception) as exc:
        ProviderResolver().text(Capability.STRUCTURED_GENERATION)
    assert exc.value.code == "AI_NOT_CONFIGURED"


async def _create_offer(client: AsyncClient) -> str:
    created = await client.post(
        "/api/v1/business/offers",
        json={
            "name": "CRM Pro",
            "description": "Партнёрка CRM",
            "category": "SaaS",
            "geo": "RU",
            "conversion_type": "sale",
            "commission_type": "percent",
            "commission_value": 20,
            "attribution_window_days": 30,
            "access_policy": "open",
            "allowed_traffic": ["seo", "telegram"],
            "forbidden_traffic": ["ppc"],
            "partner_notes": "Без брендовых запросов",
            "status": "draft",
            "product_url": "https://crmpro.example.com",
        },
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


@pytest.mark.asyncio
async def test_offer_draft_structured_and_not_saved(
    client: AsyncClient, db: AsyncSession, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-draft@example.com")
    before = await db.scalar(select(func.count(Offer.id)))
    ai_fake.queue_structured(DRAFT_PAYLOAD)

    response = await client.post(
        "/api/v1/ai/offers/draft",
        json={
            "description": "Онлайн-курс английского языка для IT-специалистов. Стоимость 30000 рублей.",
            "category": "Education",
            "product_url": "https://example.com/course",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["generation_id"]
    assert body["draft"]["name"] == "English for IT"
    assert body["draft"]["category"] == "Education"
    assert "destination_url" not in body["draft"]
    assert body["recommendations"]["commission_value"] == 15

    db.expire_all()
    after = await db.scalar(select(func.count(Offer.id)))
    assert after == before

    usage = (
        await db.execute(select(AiUsage).where(AiUsage.generation_id == body["generation_id"]))
    ).scalar_one()
    assert usage.status == "succeeded"
    assert usage.operation == Operation.OFFER_CREATE_DRAFT.value
    assert usage.provider == "fake"
    assert usage.model == "fake-model"
    assert usage.prompt_version == "offer-create-v4"
    assert usage.input_tokens == 11
    assert usage.output_tokens == 7
    assert usage.total_tokens == 18
    assert usage.cached_input_tokens == 2
    assert usage.entity_type == "OFFER"
    assert usage.entity_id is None
    assert usage.provider_metadata
    assert usage.provider_request_id == "fake-req"


@pytest.mark.asyncio
async def test_offer_draft_skips_website_fetch_without_url(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider, stub_website
):
    await register_business(client, "ai-draft-nourl@example.com")
    ai_fake.queue_structured(DRAFT_PAYLOAD)
    response = await client.post("/api/v1/ai/offers/draft", json={"description": "Курс английского"})
    assert response.status_code == 200, response.text
    assert stub_website.calls == []
    assert response.json()["website"]["status"] == "skipped"
    assert response.json()["image_url"] is None


@pytest.mark.asyncio
async def test_offer_draft_uses_website_context_in_prompt(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider, monkeypatch
):
    await register_business(client, "ai-draft-site@example.com")

    async def fake_ok(url: str):
        from app.modules.ai.website.models import WebsiteContext

        return WebsiteContext(
            source_url=url,
            status="ok",
            title="Сайт CRM",
            main_text="Облачная CRM для продаж",
        )

    monkeypatch.setattr(
        "app.modules.ai.application.offer.generate_offer_draft.load_website_context",
        fake_ok,
    )
    ai_fake.queue_structured(DRAFT_PAYLOAD)
    response = await client.post(
        "/api/v1/ai/offers/draft",
        json={"description": "Партнёрка CRM. Целевое действие — регистрация.", "product_url": "https://crm.example"},
    )
    assert response.status_code == 200, response.text
    prompt = ai_fake.calls[0].user_prompt
    assert "Сайт CRM" in prompt
    assert "Облачная CRM для продаж" in prompt
    assert "Целевое действие — регистрация" in prompt
    assert response.json()["website"]["status"] == "ok"


@pytest.mark.asyncio
async def test_offer_draft_continues_when_website_unavailable(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-draft-down@example.com")
    ai_fake.queue_structured(DRAFT_PAYLOAD)
    response = await client.post(
        "/api/v1/ai/offers/draft",
        json={"description": "Курс", "product_url": "https://down.example/course"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["website"]["status"] == "unavailable"
    assert response.json()["draft"]["name"] == "English for IT"


@pytest.mark.asyncio
async def test_offer_draft_invalid_ai_response_is_recorded(
    client: AsyncClient, db: AsyncSession, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-bad@example.com")
    ai_fake.queue_structured({"unexpected": True})
    response = await client.post("/api/v1/ai/offers/draft", json={"description": "Курс английского"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert "openai" not in response.json()["error"]["message"].lower()

    usage = (await db.execute(select(AiUsage).order_by(AiUsage.id.desc()))).scalars().first()
    assert usage is not None
    assert usage.status == "failed"
    assert usage.error_code == "AI_INVALID_RESPONSE"
    assert usage.operation == Operation.OFFER_CREATE_DRAFT.value


@pytest.mark.asyncio
async def test_failed_provider_call_records_usage(
    client: AsyncClient, db: AsyncSession, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-fail@example.com")
    ai_fake.fail_with(ai_timeout())
    response = await client.post("/api/v1/ai/offers/draft", json={"description": "Курс"})
    assert response.status_code == 504
    usage = (await db.execute(select(AiUsage).order_by(AiUsage.id.desc()))).scalars().first()
    assert usage.status == "failed"
    assert usage.error_code == "AI_TIMEOUT"


@pytest.mark.asyncio
async def test_offer_edit_returns_patch_and_drops_unsolicited_rules(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-edit@example.com")
    offer_id = await _create_offer(client)
    ai_fake.queue_structured(
        {
            "changes": [
                {"field": "description", "new_value": "Оффер для Telegram-каналов", "reason": "Канал"},
                {
                    "field": "allowed_traffic",
                    "new_value": '["telegram","content"]',
                    "reason": "Telegram",
                },
                {"field": "commission_value", "new_value": "99", "reason": "незапрошенное"},
            ]
        }
    )
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/edit",
        json={"instruction": "Сделай оффер более подходящим для продвижения через Telegram. Комиссию не меняй."},
    )
    assert response.status_code == 200, response.text
    changes = response.json()["changes"]
    fields = {item["field"] for item in changes}
    assert "description" in fields
    assert "allowed_traffic" in fields
    assert "commission_value" not in fields
    assert all(item["kind"] == "content" for item in changes)


@pytest.mark.asyncio
async def test_offer_edit_uses_form_context_as_old_value(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-edit-context@example.com")
    offer_id = await _create_offer(client)
    ai_fake.queue_structured(
        {"changes": [{"field": "name", "new_value": "Партнёрская CRM", "reason": "черновик"}]}
    )
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/edit",
        json={
            "instruction": "Переименуй оффер",
            "context": {"name": "Черновик из формы"},
        },
    )
    assert response.status_code == 200, response.text
    change = next(item for item in response.json()["changes"] if item["field"] == "name")
    assert change["old_value"] == "Черновик из формы"
    assert '"name": "Черновик из формы"' in ai_fake.calls[0].user_prompt


@pytest.mark.asyncio
async def test_offer_edit_ownership(client: AsyncClient, ai_fake: FakeTextGenerationProvider):
    await register_business(client, "ai-owner@example.com")
    offer_id = await _create_offer(client)
    await register_business(client, "ai-other@example.com", name="Other", website="https://other.example.com")
    ai_fake.queue_structured({"changes": [{"field": "description", "new_value": "x", "reason": "x"}]})
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/edit",
        json={"instruction": "Сделай описание короче"},
    )
    assert response.status_code == 404
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_rewrite_field_changes_only_requested_field(
    client: AsyncClient, ai_fake: FakeTextGenerationProvider
):
    await register_business(client, "ai-rewrite@example.com")
    offer_id = await _create_offer(client)
    ai_fake.queue_structured({"value": "CRM Pro для партнёров"})
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/fields/name/rewrite",
        json={"preset": "selling"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["field"] == "name"
    assert body["value"] == "CRM Pro для партнёров"
    assert list(body.keys()) == ["generation_id", "field", "value"]
    request = ai_fake.calls[0]
    assert request.prompt_version == "offer-field-rewrite-v6"
    assert '"field": "name"' in request.user_prompt
    assert '"preset": "selling"' in request.user_prompt
    assert '"USER_GUIDANCE":' not in request.user_prompt
    assert '"trustedInstruction"' in request.user_prompt


@pytest.mark.asyncio
async def test_rewrite_rejects_custom_guidance(client: AsyncClient, ai_fake: FakeTextGenerationProvider):
    await register_business(client, "ai-rewrite-custom@example.com")
    offer_id = await _create_offer(client)
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/fields/name/rewrite",
        json={"preset": "selling", "guidance": "добавь результат 4+4"},
    )
    assert response.status_code == 422
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_rewrite_rejects_instruction_only(client: AsyncClient, ai_fake: FakeTextGenerationProvider):
    await register_business(client, "ai-rewrite-instruction@example.com")
    offer_id = await _create_offer(client)
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/fields/name/rewrite",
        json={"instruction": "сделать более продающим"},
    )
    assert response.status_code == 422
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_rewrite_rejects_unknown_preset(client: AsyncClient, ai_fake: FakeTextGenerationProvider):
    await register_business(client, "ai-rewrite-unknown@example.com")
    offer_id = await _create_offer(client)
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/fields/name/rewrite",
        json={"preset": "youthful"},
    )
    assert response.status_code == 422
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_rewrite_unsupported_field(client: AsyncClient):
    await register_business(client, "ai-rewrite-bad@example.com")
    offer_id = await _create_offer(client)
    response = await client.post(
        f"/api/v1/ai/offers/{offer_id}/fields/commission_value/rewrite",
        json={"preset": "selling"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_generation_feedback(client: AsyncClient, db: AsyncSession, ai_fake: FakeTextGenerationProvider):
    await register_business(client, "ai-feedback@example.com")
    ai_fake.queue_structured(DRAFT_PAYLOAD)
    draft = await client.post("/api/v1/ai/offers/draft", json={"description": "Курс английского"})
    generation_id = draft.json()["generation_id"]
    feedback = await client.post(
        f"/api/v1/ai/generations/{generation_id}/feedback",
        json={
            "outcome": "EDITED_AFTER_GENERATION",
            "generated_fields_count": 8,
            "accepted_fields_count": 6,
            "modified_fields_count": 2,
            "rejected_fields_count": 0,
        },
    )
    assert feedback.status_code == 200
    usage = (await db.execute(select(AiUsage).where(AiUsage.generation_id == generation_id))).scalar_one()
    assert usage.feedback_outcome == "EDITED_AFTER_GENERATION"
    assert usage.accepted_fields_count == 6


@pytest.mark.asyncio
async def test_ai_requires_business_role(client: AsyncClient):
    response = await client.post("/api/v1/ai/offers/draft", json={"description": "Курс"})
    assert response.status_code == 401


def test_openai_quota_is_not_mapped_as_rate_limit():
    error = map_provider_http_error(
        429,
        {"error": {"code": "insufficient_quota", "type": "insufficient_quota"}},
    )
    assert error.code == "AI_QUOTA_EXCEEDED"
    assert error.status_code == 503
    assert error.provider_metadata["http_status"] == 429
    assert is_retryable_provider_error(429, {"error": {"code": "insufficient_quota"}}) is False


def test_openai_rate_limit_is_retryable():
    error = map_provider_http_error(429, {"error": {"code": "rate_limit_exceeded", "type": "rate_limit_exceeded"}})
    assert error.code == "AI_RATE_LIMIT"
    assert is_retryable_provider_error(429, {"error": {"code": "rate_limit_exceeded"}}) is True


def test_openai_unknown_model_is_mapped():
    error = map_provider_http_error(404, {"error": {"code": "model_not_found", "type": "invalid_request_error"}})
    assert error.code == "AI_MODEL_UNAVAILABLE"
    assert is_retryable_provider_error(404, {"error": {"code": "model_not_found"}}) is False


def test_openai_invalid_model_message_is_mapped():
    error = map_provider_http_error(
        400,
        {
            "error": {
                "message": "Invalid model 'gpt-5.4-luna' for this endpoint",
                "type": "invalid_request_error",
                "code": "invalid_value",
            }
        },
    )
    assert error.code == "AI_MODEL_UNAVAILABLE"
    assert "gpt-5.4-luna" in (error.provider_metadata.get("provider_error_message") or "")


TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _image_client(monkeypatch, handler):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *args, **kwargs):
            return handler(url, kwargs.get("json") or {})

    monkeypatch.setattr("app.modules.ai.providers.openai_image.httpx.AsyncClient", FakeAsyncClient)


def _image_request(**overrides) -> ImageGenerationRequest:
    payload = {
        "prompt": "square product photo",
        "aspect_ratio": "1:1",
        "image_format": "square_1_1",
        "operation": "PROMO_IMAGE_GENERATE",
        "prompt_version": "promo-image-v1",
    }
    payload.update(overrides)
    return ImageGenerationRequest(**payload)


@pytest.mark.asyncio
async def test_openai_image_luna_uses_responses_api(monkeypatch):
    captured: dict = {}

    def handler(url, payload):
        captured["url"] = url
        captured["json"] = payload
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "model": "gpt-5.4-luna",
                "output": [
                    {
                        "type": "image_generation_call",
                        "status": "completed",
                        "result": TINY_PNG_B64,
                        "revised_prompt": "product on white",
                    }
                ],
                "usage": {"input_tokens": 12, "output_tokens": 40, "total_tokens": 52},
            },
        )

    _image_client(monkeypatch, handler)
    from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider

    provider = OpenAIImageGenerationProvider(api_key="sk-test", model="gpt-5.4-luna", max_retries=0)
    result = await provider.generate(_image_request())
    assert captured["url"].endswith("/responses")
    assert captured["json"]["model"] == "gpt-5.4-luna"
    assert captured["json"]["tools"][0]["type"] == "image_generation"
    assert captured["json"]["tools"][0]["size"] == "1024x1024"
    assert result.images
    assert result.images[0].mime_type == "image/png"
    assert result.provider_metadata["api"] == "responses"


@pytest.mark.asyncio
async def test_openai_image_gpt_image_uses_images_api(monkeypatch):
    captured: dict = {}

    def handler(url, payload):
        captured["url"] = url
        captured["json"] = payload
        return httpx.Response(
            200,
            json={"created": 1, "data": [{"b64_json": TINY_PNG_B64}]},
        )

    _image_client(monkeypatch, handler)
    from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider

    provider = OpenAIImageGenerationProvider(api_key="sk-test", model="gpt-image-1", max_retries=0)
    result = await provider.generate(_image_request())
    assert captured["url"].endswith("/images/generations")
    assert captured["json"]["model"] == "gpt-image-1"
    assert result.provider_metadata["api"] == "images"
    assert result.usage.provider_request_id == "1"


@pytest.mark.asyncio
async def test_openai_image_created_timestamp_is_string_request_id(monkeypatch):
    def handler(url, payload):
        return httpx.Response(
            200,
            json={"created": 1787925019, "data": [{"b64_json": TINY_PNG_B64}]},
        )

    _image_client(monkeypatch, handler)
    from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider

    provider = OpenAIImageGenerationProvider(api_key="sk-test", model="gpt-image-1-mini", max_retries=0)
    result = await provider.generate(_image_request())
    assert result.usage.provider_request_id == "1787925019"
    assert isinstance(result.usage.provider_request_id, str)


@pytest.mark.asyncio
async def test_openai_image_http_error_keeps_provider_message(monkeypatch):
    def handler(url, payload):
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid model 'gpt-5.4-luna' for /v1/images/generations",
                    "type": "invalid_request_error",
                    "code": "invalid_value",
                }
            },
        )

    _image_client(monkeypatch, handler)
    from app.modules.ai.providers.openai_image import OpenAIImageGenerationProvider

    provider = OpenAIImageGenerationProvider(api_key="sk-test", model="gpt-image-1", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(_image_request())
    assert exc.value.code == "AI_MODEL_UNAVAILABLE"
    assert "images/generations" in (exc.value.provider_metadata.get("provider_error_message") or "")
    assert exc.value.provider_metadata.get("endpoint") == "/images/generations"


@pytest.mark.asyncio
async def test_openai_quota_does_not_retry(monkeypatch):
    calls = {"n": 0}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            calls["n"] += 1
            return httpx.Response(
                429,
                json={"error": {"code": "insufficient_quota", "type": "insufficient_quota"}},
            )

    monkeypatch.setattr("app.modules.ai.providers.openai_text.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAITextGenerationProvider(api_key="sk-test", model="gpt-4o", max_retries=1)
    with pytest.raises(Exception) as exc:
        await provider.generate_structured(
            StructuredGenerationRequest(
                system_prompt="sys",
                user_prompt="user",
                schema={"type": "object"},
                schema_name="test",
                operation="OFFER_CREATE_DRAFT",
                prompt_version="offer-create-v1",
            )
        )
    assert exc.value.code == "AI_QUOTA_EXCEEDED"
    assert calls["n"] == 1
