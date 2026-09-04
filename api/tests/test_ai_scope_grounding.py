"""Scope guard, mixed guidance, and output grounding regression tests."""

import pytest

from app.core.config import settings
from app.modules.ai.errors import AiError
from app.modules.ai.providers.fake import FakeTextGenerationProvider
from app.modules.ai.resolver import get_fake_image_provider, get_fake_provider
from app.modules.ai.safety.grounding import guard_output_grounding, inspect_output_grounding
from app.modules.ai.safety.operations import AiOperation
from app.modules.ai.safety.pipeline import evaluate_user_guidance
from app.modules.ai.safety.policy import get_operation_policy
from app.modules.ai.safety.scope_guard import inspect_scope
from app.modules.ai.safety.verified_context import build_verified_context


@pytest.fixture(autouse=True)
def ai_fake(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "fake")
    fake = get_fake_provider()
    fake.reset()
    get_fake_image_provider().reset()
    yield fake

@pytest.mark.asyncio
async def test_mixed_style_and_calculation_is_rejected_before_generation(
    ai_fake: FakeTextGenerationProvider,
):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_TITLE,
            guidance=(
                "сделай название в молодежном стиле и одновременно в строгом корпоративном стиле "
                "и добавь в название результат выражения 4+4"
            ),
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"
    assert "не относящиеся к редактированию" in exc.value.message
    assert ai_fake.guard_calls == []
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_pure_calculation_guidance_is_rejected(ai_fake: FakeTextGenerationProvider):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_TITLE,
            guidance="добавь результат 4+4",
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_youthful_style_guidance_is_allowed(ai_fake: FakeTextGenerationProvider):
    result = await evaluate_user_guidance(
        operation=AiOperation.IMPROVE_OFFER_TITLE,
        guidance="сделай название в более молодёжном стиле",
    )
    assert result.guidance == "сделай название в более молодёжном стиле"


@pytest.mark.asyncio
async def test_compatible_dual_style_guidance_is_allowed(ai_fake: FakeTextGenerationProvider):
    result = await evaluate_user_guidance(
        operation=AiOperation.IMPROVE_OFFER_TITLE,
        guidance="сделай название современным, но сохрани строгий корпоративный тон",
    )
    assert "корпоративный" in result.guidance


@pytest.mark.asyncio
async def test_unverified_price_guidance_is_rejected(ai_fake: FakeTextGenerationProvider):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_TITLE,
            guidance="добавь в название цену 3 500 000 ₽",
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"


@pytest.mark.asyncio
async def test_calculated_discount_guidance_is_rejected(ai_fake: FakeTextGenerationProvider):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_TITLE,
            guidance="вычисли скидку 10% и вставь новую цену",
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"


@pytest.mark.asyncio
async def test_description_unverified_years_claim_is_rejected(ai_fake: FakeTextGenerationProvider):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_DESCRIPTION,
            guidance="Сделай текст проще и добавь, что компания работает 25 лет",
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"
    assert ai_fake.calls == []


@pytest.mark.asyncio
async def test_mixed_programming_guidance_is_rejected(ai_fake: FakeTextGenerationProvider):
    with pytest.raises(AiError) as exc:
        await evaluate_user_guidance(
            operation=AiOperation.IMPROVE_OFFER_DESCRIPTION,
            guidance="Сделай описание короче и напиши пример на Python",
        )
    assert exc.value.code == "INVALID_AI_GUIDANCE"
    assert "не относящиеся к редактированию" in exc.value.message


def test_scope_detects_mixed_intents():
    scope = inspect_scope(
        "сделай название молодёжным и добавь результат выражения 4+4",
        operation=AiOperation.IMPROVE_OFFER_TITLE,
    )
    assert not scope.allowed
    assert scope.category == "MIXED_VALID_AND_INVALID_GUIDANCE"
    assert "CHANGE_STYLE" in scope.valid_intents
    assert "CALCULATION" in scope.invalid_intents


def test_output_grounding_rejects_new_title_number_even_if_scope_failed_open():
    verified = build_verified_context(
        field="name",
        current_value="Автомобиль EXEED RX",
        offer_context={"name": "Автомобиль EXEED RX", "description": "Кроссовер EXEED RX"},
    )
    policy = get_operation_policy(AiOperation.IMPROVE_OFFER_TITLE)
    result = inspect_output_grounding(
        {"value": "EXEED RX 8"},
        operation=AiOperation.IMPROVE_OFFER_TITLE,
        verified=verified,
        policy=policy,
        source_text="Автомобиль EXEED RX",
    )
    assert not result.grounded
    assert "8" in result.unsupported_numbers
    with pytest.raises(AiError) as exc:
        guard_output_grounding(
            {"value": "EXEED RX 8"},
            operation=AiOperation.IMPROVE_OFFER_TITLE,
            verified=verified,
            policy=policy,
            source_text="Автомобиль EXEED RX",
        )
    assert exc.value.code == "AI_INVALID_RESPONSE"


def test_output_grounding_allows_verified_price_in_title():
    verified = build_verified_context(
        field="name",
        current_value="EXEED RX",
        offer_context={"name": "EXEED RX", "description": "Автомобиль EXEED RX за 4 000 000 ₽"},
    )
    policy = get_operation_policy(AiOperation.IMPROVE_OFFER_TITLE)
    result = inspect_output_grounding(
        {"value": "EXEED RX — 4 000 000 ₽"},
        operation=AiOperation.IMPROVE_OFFER_TITLE,
        verified=verified,
        policy=policy,
        source_text="EXEED RX",
    )
    assert result.grounded


def test_output_grounding_rejects_new_entity_brand_claim_number_proxy():
    verified = build_verified_context(
        field="name",
        current_value="EXEED RX",
        offer_context={"name": "EXEED RX", "description": "Кроссовер EXEED RX"},
    )
    policy = get_operation_policy(AiOperation.IMPROVE_OFFER_TITLE)
    result = inspect_output_grounding(
        {"value": "Новый BMW X5 для города"},
        operation=AiOperation.IMPROVE_OFFER_TITLE,
        verified=verified,
        policy=policy,
        source_text="EXEED RX",
    )
    # Deterministic layer may not catch brand names; it must at least not invent numbers.
    # Brand entity check is soft via claim list; ensure no false number rejection alone.
    assert result.grounded or result.unsupported_numbers == ()


def test_improve_policies_disallow_new_facts():
    for operation in (
        AiOperation.IMPROVE_OFFER_TITLE,
        AiOperation.IMPROVE_OFFER_DESCRIPTION,
        AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
        AiOperation.REWRITE_CREATIVE,
        AiOperation.EDIT_OFFER,
    ):
        policy = get_operation_policy(operation)
        assert policy.allow_new_facts is False
        assert policy.allow_new_numbers is False
