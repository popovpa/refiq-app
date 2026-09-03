import pytest

from app.modules.ai.application.creative.promo_image_prompt import compact_image_prompt_to_limit
from app.modules.ai.prompts.promo import image_spec_system_prompt

_LONG_SPEC = {
    "concept": "premium_city",
    "format": "1:1",
    "subject": "EXEED RX",
    "audience": "покупатели автомобиля",
    "visualDirection": "premium automotive photography",
    "headline": "EXEED RX",
    "cta": "Запишитесь на тест-драйв",
    "imagePrompt": (
        "Премиальный рекламный баннер автомобиля EXEED RX для потенциального покупателя. "
        "Автомобиль крупным планом на современном городском фоне, реалистичная коммерческая "
        "автомобильная фотография с мягким вечерним светом, мокрый асфальт и стеклянные фасады. "
        "Использовать только текст: «EXEED RX» «Запишитесь на тест-драйв». "
        "Никаких других надписей, логотипов партнёрских программ и постороннего текста не добавлять. "
    )
    * 3,
}


def test_compact_keeps_complete_sentences_under_limit():
    prompt = (
        "Премиальный рекламный баннер автомобиля EXEED RX для потенциального покупателя. "
        "Автомобиль крупным планом на современном городском фоне. "
        "Реалистичная коммерческая автомобильная фотография с мягким вечерним светом. "
        "Использовать только текст: «EXEED RX» «Запишитесь на тест-драйв»."
    )
    compacted = compact_image_prompt_to_limit(prompt, limit=180)
    assert len(compacted) <= 180
    assert compacted.endswith(".")
    assert "EXEED RX" in compacted
    assert prompt[: len(compacted)] == compacted or compacted in prompt


def test_compact_does_not_cut_mid_word():
    prompt = "EXEED RX премиальный городской кроссовер для покупателя на вечерней улице"
    compacted = compact_image_prompt_to_limit(prompt, limit=28)
    assert len(compacted) <= 28
    assert not compacted.endswith("кросс")
    assert compacted.split()[-1] in prompt.split()


def test_compact_noop_when_already_short():
    prompt = "EXEED RX, только текст «EXEED RX»."
    assert compact_image_prompt_to_limit(prompt, limit=500) == prompt


def test_image_spec_prompt_has_no_character_cap():
    text = image_spec_system_prompt()
    assert "no character cap" not in text
    assert "без лимита символов" in text
    assert "HARD LIMIT" not in text
    assert "Alice AI ART" not in text
    assert "PRODUCT_CONTEXT.description" in text or "mustReflectInScene" in text
    assert "визуально передавать конкретные условия" in text
    assert "NO CTA buttons" not in text
    assert "НЕ содержать CTA-кнопок" in text
    assert "headline and CTA only" not in text
    compact = image_spec_system_prompt(compact=True)
    assert "ПЕРЕПИШИТЕ" in compact
    assert "лимита символов" in compact
    assert "CTA-кнопки" in compact


@pytest.mark.asyncio
async def test_long_image_spec_is_accepted_without_truncation(monkeypatch):
    from app.core.config import settings
    from app.modules.ai.application.creative.promo_kit import generate_image_specification
    from app.modules.ai.context.offer_context import OfferPromotionContextBuilder
    from app.modules.ai.resolver import get_fake_provider
    from app.modules.offers.models import Offer, OfferCommissionRule

    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "fake")
    offer = Offer(
        id=1,
        business_id=1,
        name="EXEED RX",
        description="Премиальный кроссовер",
        category="Авто",
        geo="RU",
        conversion_type="sale",
        commission_rules=[OfferCommissionRule(type="fixed", value=50000, currency="RUB")],
    )
    fake = get_fake_provider()
    fake.reset()
    fake.queue_structured(_LONG_SPEC)
    spec = await generate_image_specification(
        offer_id=1,
        user_id=1,
        context=OfferPromotionContextBuilder().from_offer(offer),
        brief={"promotedProduct": "EXEED RX", "cta": "Запишитесь на тест-драйв"},
        concept="EXEED RX в городе",
        aspect="1:1",
        qr_safe=False,
        run_id=1,
        item_id=64,
    )
    assert _LONG_SPEC["imagePrompt"].strip() in spec["imagePrompt"]
    assert "Описание оффера (обязательно отразить в сцене): Премиальный кроссовер" in spec["imagePrompt"]
    assert spec["imagePrompt"].startswith("Описание оффера (обязательно отразить в сцене):")
    assert len(spec["imagePrompt"]) > 500
    assert "EXEED RX" in spec["imagePrompt"]
    assert "комисс" not in spec["imagePrompt"].lower()
    assert "50 000" not in spec["imagePrompt"]


def test_image_prompt_keeps_full_offer_description_up_front():
    from app.modules.ai.application.creative.promo_kit import _with_offer_description

    description = (
        "Продаём подержанные автомобили старше 50 лет для аудитории старше 60 лет. "
        "Фокус на классических моделях и спокойной подаче."
    )
    prompt = _with_offer_description(
        "Premium car advertisement, modern showroom lighting.",
        {"productContext": {"description": description}},
    )
    assert prompt.startswith(f"Описание оффера (обязательно отразить в сцене): {description}")
    assert "Premium car advertisement" in prompt
    assert "старше 50 лет" in prompt
    assert "старше 60 лет" in prompt


def test_square_slot_generates_one_image():
    from app.modules.creatives.promo_catalog import SLOTS

    assert SLOTS["images_1_1"].image_count == 1
    assert SLOTS["images_16_9"].image_count == 1
    assert SLOTS["images_9_16"].image_count == 1
