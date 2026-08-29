import pytest

from app.modules.ai.application.creative.promo_copy_guard import (
    assert_customer_facing_copy,
    looks_like_affiliate_recruiting,
)
from app.modules.ai.application.creative.promo_kit import _sanitize_brief
from app.modules.ai.context.offer_context import OfferPromotionContextBuilder
from app.modules.ai.context.promo_payload import brief_user_payload, text_generation_payload
from app.modules.ai.errors import AiError
from app.modules.ai.prompts.promo import image_prompt
from app.modules.offers.models import Offer, OfferCommissionRule
from app.modules.products.models import Product


def _car_offer() -> Offer:
    return Offer(
        id=1,
        business_id=1,
        name="Авто из салона",
        description="Новый городской автомобиль с современными системами помощи водителю. Доступен тест-драйв.",
        category="Авто",
        geo="RU",
        conversion_type="sale",
        partner_notes="Комиссия 50 000 ₽ за продажу. Только SEO и контент.",
        allowed_traffic=["seo", "content"],
        forbidden_traffic=["ppc", "brand"],
        commission_rules=[
            OfferCommissionRule(type="fixed", value=50000, currency="RUB"),
        ],
    )


def test_promo_context_is_customer_acquisition_and_hides_commission():
    payload = OfferPromotionContextBuilder().from_offer(_car_offer())
    dumped_public = str(payload["productContext"]) + str(payload["offer"])
    dumped_all = str(payload)
    assert payload["purpose"] == "CUSTOMER_ACQUISITION"
    assert payload["targetAudienceRole"] == "END_CUSTOMER"
    assert payload["promotedObject"] == "PRODUCT_OR_SERVICE"
    assert payload["productContext"]["name"] == "Авто из салона"
    assert payload["productContext"]["customerAction"] == "purchase"
    assert "50 000" not in dumped_all
    assert "50000" not in dumped_all
    assert "commission_value" not in dumped_all
    assert "комисс" not in dumped_public.lower()
    assert payload["offer"].get("partner_notes") is None
    notes = payload["affiliateConstraints"]["partnerNotes"]
    assert "комисс" not in notes.lower()
    assert "SEO" in notes or "контент" in notes.lower()
    assert payload["affiliateConstraints"]["mustNotAppearInCustomerCreative"] is True
    assert payload["affiliateConstraints"]["useAsComplianceOnly"] is True


def test_product_model_wins_over_offer_name():
    offer = _car_offer()
    product = Product(id=2, business_id=1, name="City Hatch 2024", description="Компактный хэтчбек для города.", url="https://cars.example.com/hatch")
    payload = OfferPromotionContextBuilder().from_offer(offer, product=product)
    assert payload["productContext"]["name"] == "City Hatch 2024"
    assert payload["productContext"]["landingPage"] == "https://cars.example.com/hatch"
    assert payload["productContext"]["description"].startswith("Компактный")


def test_thin_product_context_is_flagged():
    offer = Offer(
        id=3,
        business_id=1,
        name="Оффер",
        description="",
        conversion_type="sale",
        commission_rules=[],
    )
    payload = OfferPromotionContextBuilder().from_offer(offer)
    assert payload["productContext"]["contextLimited"] is True


def test_brief_and_text_payloads_keep_affiliate_internal():
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    brief_payload = brief_user_payload(snapshot)
    assert "commission" not in str(brief_payload["productContext"]).lower()
    assert "50 000" not in str(brief_payload)
    assert "50000" not in str(brief_payload)
    assert "комисс" not in str(brief_payload).lower()
    assert brief_payload["purpose"] == "CUSTOMER_ACQUISITION"
    assert brief_payload["materialPurpose"] == "CUSTOMER_ACQUISITION"
    assert brief_payload["productContext"]["name"] == "Авто из салона"
    assert brief_payload["affiliateConstraints"]["internalOnly"] is True

    text_payload = text_generation_payload(
        snapshot,
        {"cta": "Записаться на тест-драйв", "keyBenefits": ["Комфорт", "Помощь водителю"]},
        "telegram_posts",
    )
    public = str(text_payload)
    assert text_payload["purpose"] == "CUSTOMER_ACQUISITION"
    assert "50000" not in public
    assert "комисс" not in public.lower()
    assert text_payload["affiliateConstraints"]["useAsComplianceOnly"] is True
    assert "partner_notes" not in (text_payload.get("productContext") or {})


def test_image_prompt_advertises_car_not_commission():
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    prompt = image_prompt(
        snapshot,
        {
            "mainValueProposition": "Комфорт и технологии для ежедневных поездок",
            "keyBenefits": ["Помощь водителю", "Городской комфорт"],
            "cta": "Записаться на тест-драйв",
            "visualDirection": "Чистый студийный кадр автомобиля",
            "creativeConcepts": ["Партнёрская программа", "Автомобиль на вечерней улице"],
        },
        "Автомобиль на вечерней улице",
        aspect="1:1",
    )
    lower = prompt.lower()
    assert "customer acquisition" in lower
    assert "авто из салона" in lower
    assert "тест-драйв" in lower
    assert "50 000" not in prompt
    assert "50000" not in prompt
    assert "партнёрская программа" not in lower
    assert "allowed_traffic" not in lower
    assert "partner_notes" not in lower
    assert "комиссия 50" not in lower


def test_image_prompt_drops_affiliate_concept():
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    prompt = image_prompt(
        snapshot,
        {"mainValueProposition": "Комфорт для ежедневных поездок", "cta": "Узнать комплектации"},
        "Партнёрская программа. 50 000 ₽ за продажу",
    )
    lower = prompt.lower()
    assert "партнёрская программа" not in lower
    assert "50 000" not in prompt
    assert "комфорт для ежедневных поездок" in lower


def test_qr_image_prompt_uses_customer_cta():
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    prompt = image_prompt(
        snapshot,
        {"cta": "Записаться на тест-драйв", "mainValueProposition": "Городской автомобиль"},
        "Автомобиль у салона",
        qr_safe=True,
    )
    lower = prompt.lower()
    assert "never write «qr партнёра»" in lower
    assert "партнёрская ссылка" in lower
    assert "записаться на тест-драйв" in lower
    assert "do not draw any qr code" in lower


def test_medical_service_image_prompt_omits_commission():
    offer = Offer(
        id=4,
        business_id=1,
        name="УЗИ брюшной полости",
        description="УЗИ органов брюшной полости в клинике в Вельске. Приём по записи.",
        category="Медицина",
        geo="Вельск",
        conversion_type="lead",
        partner_notes="CPA 800 ₽ за заявку",
        allowed_traffic=["seo"],
        forbidden_traffic=[],
        commission_rules=[OfferCommissionRule(type="fixed", value=800, currency="RUB")],
    )
    snapshot = OfferPromotionContextBuilder().from_offer(offer)
    prompt = image_prompt(
        snapshot,
        {"cta": "Записаться", "mainValueProposition": "УЗИ по записи в Вельске"},
        "Спокойный медицинский кабинет",
    )
    assert "узи" in prompt.lower()
    assert "800 ₽" not in prompt
    assert "800" not in prompt.split("STRICT RULES")[0]
    assert "комиссия" not in prompt.lower()


def test_copy_guard_rejects_affiliate_recruiting():
    product = {"name": "Городской автомобиль", "description": "Комфорт для ежедневных поездок"}
    assert looks_like_affiliate_recruiting(
        "Партнёрская программа. Получайте комиссию 50 000 ₽ за каждый проданный автомобиль.",
        product_context=product,
    )
    with pytest.raises(AiError) as exc:
        assert_customer_facing_copy(
            {"headline": "Партнёрская программа", "body": "50 000 ₽ за продажу", "cta": "Подключить оффер"},
            product_context=product,
        )
    assert exc.value.code == "AI_INVALID_RESPONSE"


def test_copy_guard_allows_product_that_is_a_partner_platform():
    product = {
        "name": "CRM Pro",
        "description": "Партнёрская программа и кабинет сделок для SaaS-команд",
    }
    assert not looks_like_affiliate_recruiting(
        "Партнёрская программа и кабинет сделок в одном окне.",
        product_context=product,
    )


def test_copy_guard_allows_neutral_product_ads():
    product = {"name": "УЗИ брюшной полости", "description": "Исследование по записи"}
    assert not looks_like_affiliate_recruiting(
        "УЗИ брюшной полости в Вельске. Запишитесь на приём.",
        product_context=product,
    )


def test_affiliate_only_description_is_not_used_as_product_copy():
    offer = Offer(
        id=5,
        business_id=1,
        name="Автомобиль",
        description="Комиссия 50 000 ₽ за продажу. CPA за каждый проданный автомобиль.",
        category="Авто",
        conversion_type="sale",
        commission_rules=[OfferCommissionRule(type="fixed", value=50000, currency="RUB")],
    )
    payload = OfferPromotionContextBuilder().from_offer(offer)
    assert "50 000" not in payload["productContext"]["description"]
    assert "комисс" not in payload["productContext"]["description"].lower()
    assert payload["productContext"]["contextLimited"] is True
    prompt = image_prompt(payload, {"cta": "Узнать комплектации"}, "Автомобиль в городе")
    assert "50 000" not in prompt
    assert "комисс" not in prompt.lower()


def test_sanitize_brief_drops_affiliate_concepts_and_cta():
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    cleaned = _sanitize_brief(
        {
            "purpose": "PARTNER_RECRUITMENT",
            "creativeConcepts": ["Партнёрская программа", "Автомобиль на вечерней улице"],
            "keyBenefits": ["50 000 ₽ за продажу", "Комфорт в городе"],
            "cta": "Стать партнёром",
            "mainValueProposition": "Получайте комиссию за каждый автомобиль",
            "promotedProduct": "",
        },
        snapshot,
    )
    assert cleaned["purpose"] == "CUSTOMER_ACQUISITION"
    assert cleaned["creativeConcepts"] == ["Автомобиль на вечерней улице"]
    assert cleaned["keyBenefits"] == ["Комфорт в городе"]
    assert cleaned["cta"] == "Узнать подробнее"
    assert "комисс" not in (cleaned["mainValueProposition"] or "").lower()
    assert cleaned["promotedProduct"] == "Авто из салона"


def test_promo_brief_schema_is_openai_strict():
    from app.modules.ai.schemas import promo_brief_schema

    schema = promo_brief_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "purpose" in schema["required"]
    assert "promotedProduct" in schema["required"]
    assert "primaryCustomerNeed" in schema["required"]
    assert "verifiedProductFacts" in schema["required"]


def test_promo_image_spec_schema_is_strict():
    from app.modules.ai.schemas import promo_image_spec_schema

    schema = promo_image_spec_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert "imagePrompt" in schema["required"]


@pytest.mark.asyncio
async def test_image_spec_excludes_affiliate_economics(monkeypatch):
    from app.core.config import settings
    from app.modules.ai.application.creative.promo_kit import generate_image_specification
    from app.modules.ai.resolver import get_fake_provider

    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "fake")
    snapshot = OfferPromotionContextBuilder().from_offer(_car_offer())
    fake = get_fake_provider()
    fake.reset()
    fake.queue_structured(
        {
            "concept": "premium_city",
            "format": "1:1",
            "subject": "EXEED RX",
            "audience": "потенциальные покупатели автомобиля",
            "visualDirection": "premium automotive commercial photography",
            "headline": "EXEED RX",
            "cta": "Запишитесь на тест-драйв",
            "imagePrompt": (
                "Премиальный рекламный баннер автомобиля EXEED RX для потенциального покупателя. "
                "Автомобиль крупным планом на современном городском фоне, реалистичная коммерческая фотография. "
                "Только текст «EXEED RX» и «Запишитесь на тест-драйв»."
            ),
        }
    )
    spec = await generate_image_specification(
        offer_id=1,
        user_id=1,
        context=snapshot,
        brief={
            "promotedProduct": "EXEED RX",
            "targetAudience": "покупатели автомобиля",
            "mainValueProposition": "Комфорт в городе",
            "cta": "Запишитесь на тест-драйв",
        },
        concept="EXEED RX в городе",
        aspect="1:1",
        qr_safe=False,
        run_id=1,
        item_id=1,
    )
    user_prompt = fake.calls[0].user_prompt
    assert "50000" not in user_prompt
    assert "commission" not in user_prompt.lower()
    assert "комисс" not in user_prompt.lower()
    assert "payout" not in user_prompt.lower()
    assert "affiliateConstraints" not in user_prompt
    prompt = spec["imagePrompt"].lower()
    assert "exeed rx" in prompt
    assert "комисс" not in prompt
    assert "50 000" not in spec["imagePrompt"]
    assert "партнёрская программа" not in prompt


@pytest.mark.asyncio
async def test_medical_image_spec_omits_commission(monkeypatch):
    from app.core.config import settings
    from app.modules.ai.application.creative.promo_kit import generate_image_specification
    from app.modules.ai.resolver import get_fake_provider

    monkeypatch.setattr(settings, "AI_PROVIDER", "fake")
    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "fake")

    offer = Offer(
        id=4,
        business_id=1,
        name="УЗИ брюшной полости",
        description="УЗИ органов брюшной полости в клинике в Вельске. Приём по записи.",
        category="Медицина",
        geo="Вельск",
        conversion_type="lead",
        partner_notes="CPA 800 ₽ за заявку",
        allowed_traffic=["seo"],
        forbidden_traffic=[],
        commission_rules=[OfferCommissionRule(type="fixed", value=800, currency="RUB")],
    )
    snapshot = OfferPromotionContextBuilder().from_offer(offer)
    fake = get_fake_provider()
    fake.reset()
    fake.queue_structured(
        {
            "concept": "clinic",
            "format": "1:1",
            "subject": "УЗИ брюшной полости",
            "audience": "пациенты",
            "visualDirection": "спокойный медицинский кабинет",
            "headline": "УЗИ брюшной полости",
            "cta": "Записаться",
            "imagePrompt": "Спокойный рекламный кадр кабинета УЗИ для пациента. Только текст «УЗИ брюшной полости» и «Записаться».",
        }
    )
    spec = await generate_image_specification(
        offer_id=4,
        user_id=1,
        context=snapshot,
        brief={"cta": "Записаться", "mainValueProposition": "УЗИ по записи в Вельске"},
        concept="Кабинет УЗИ",
        aspect="1:1",
        qr_safe=False,
        run_id=2,
        item_id=2,
    )
    assert "узи" in spec["imagePrompt"].lower()
    assert "800" not in spec["imagePrompt"]
    assert "комисс" not in spec["imagePrompt"].lower()
    assert "cpa" not in fake.calls[0].user_prompt.lower()


def test_copy_guard_rejects_sale_bounty_copy():
    product = {"name": "Городской автомобиль", "description": "Комфорт для ежедневных поездок"}
    assert looks_like_affiliate_recruiting("50 000 ₽ за продажу автомобиля", product_context=product)
