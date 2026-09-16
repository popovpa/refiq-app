from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.ai.offer_fields import (
    ACCESS_POLICIES,
    CATEGORIES,
    COMMISSION_TYPES,
    CONVERSION_TYPES,
    CURRENCIES,
    GEO_OPTIONS,
    TRAFFIC_TYPES,
)


class OfferDraftContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    category: str
    geo: str
    partner_notes: str = ""
    allowed_traffic: list[str] = Field(default_factory=list)
    forbidden_traffic: list[str] = Field(default_factory=list)
    product_url: str = ""

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name is required")
        return name[:255]

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("description is required")
        return text[:1000]

    @field_validator("category")
    @classmethod
    def category_ok(cls, value: str) -> str:
        from app.modules.catalog import resolve_category_code

        return resolve_category_code(value) or "OTHER"

    @field_validator("geo")
    @classmethod
    def geo_ok(cls, value: str) -> str:
        from app.modules.catalog import parse_geo_codes

        codes = parse_geo_codes(value)
        return ",".join(codes) if codes else "RU"

    @field_validator("allowed_traffic", "forbidden_traffic")
    @classmethod
    def traffic_ok(cls, value: list[str]) -> list[str]:
        from app.modules.catalog import normalize_traffic_source

        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            code = normalize_traffic_source(item)
            if code and code not in seen:
                seen.add(code)
                result.append(code)
        return result


class OfferRecommendations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversion_type: str = "sale"
    commission_type: str = "percent"
    commission_value: float = 10
    commission_currency: str = "RUB"
    attribution_window_days: int = 30
    access_policy: str = "open"

    @field_validator("conversion_type")
    @classmethod
    def conversion_ok(cls, value: str) -> str:
        return value if value in CONVERSION_TYPES else "sale"

    @field_validator("commission_type")
    @classmethod
    def commission_ok(cls, value: str) -> str:
        return value if value in COMMISSION_TYPES else "percent"

    @field_validator("commission_currency")
    @classmethod
    def currency_ok(cls, value: str) -> str:
        return value if value in CURRENCIES else "RUB"

    @field_validator("access_policy")
    @classmethod
    def access_ok(cls, value: str) -> str:
        return value if value in ACCESS_POLICIES else "open"

    @field_validator("commission_value")
    @classmethod
    def value_ok(cls, value: float) -> float:
        return max(0, float(value))

    @field_validator("attribution_window_days")
    @classmethod
    def window_ok(cls, value: int) -> int:
        return max(1, int(value))


class OfferDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: OfferDraftContent
    recommendations: OfferRecommendations


class OfferEditChangeRaw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    new_value: str
    reason: str = ""


class OfferEditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[OfferEditChangeRaw]


class OfferRewritePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


VARIANT_KINDS = ("short", "expert", "promotional")


class CreativeTextVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "promotional"
    headline: str
    body: str
    cta: str

    @field_validator("kind")
    @classmethod
    def kind_ok(cls, value: str) -> str:
        kind = (value or "").strip().lower()
        return kind if kind in VARIANT_KINDS else "promotional"

    @field_validator("headline", "body", "cta")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return (value or "").strip()


class CreativeSocialVariant(CreativeTextVariant):
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("hashtags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        tags: list[str] = []
        for item in value or []:
            tag = str(item).strip().lstrip("#")
            if tag and tag not in tags:
                tags.append(tag[:40])
            if len(tags) >= 5:
                break
        return tags


class CreativeTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variants: list[CreativeTextVariant]


class CreativeSocialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variants: list[CreativeSocialVariant]


class CreativeRewritePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    body: str
    cta: str
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("headline", "body", "cta")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("hashtags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return CreativeSocialVariant.clean_tags(value)


class PromoBriefPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = "CUSTOMER_ACQUISITION"
    promotedProduct: str = ""
    primaryCustomerNeed: str = ""
    targetAudience: str
    mainValueProposition: str
    keyBenefits: list[str] = Field(default_factory=list)
    verifiedProductFacts: list[str] = Field(default_factory=list)
    toneOfVoice: str
    cta: str
    restrictions: list[str] = Field(default_factory=list)
    creativeConcepts: list[str] = Field(default_factory=list)
    positioning: str = ""
    allowedClaims: list[str] = Field(default_factory=list)
    prohibitedClaims: list[str] = Field(default_factory=list)
    visualDirection: str = ""

    @field_validator("purpose")
    @classmethod
    def force_customer_acquisition(cls, value: str) -> str:
        return "CUSTOMER_ACQUISITION"

    @field_validator(
        "promotedProduct",
        "primaryCustomerNeed",
        "targetAudience",
        "mainValueProposition",
        "toneOfVoice",
        "cta",
        "positioning",
        "visualDirection",
    )
    @classmethod
    def trim_brief(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator(
        "keyBenefits",
        "verifiedProductFacts",
        "restrictions",
        "creativeConcepts",
        "allowedClaims",
        "prohibitedClaims",
    )
    @classmethod
    def trim_list(cls, value: list[str]) -> list[str]:
        items = []
        for item in value or []:
            text = str(item).strip()
            if text:
                items.append(text[:240])
        return items[:8]


class PromoCopyBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = ""
    body: str = ""
    cta: str = ""

    @field_validator("headline", "body", "cta")
    @classmethod
    def trim_copy(cls, value: str) -> str:
        return (value or "").strip()


class PromoSocialBlock(PromoCopyBlock):
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("hashtags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return CreativeSocialVariant.clean_tags(value)


class PromoKitTextsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universal_ad: PromoCopyBlock
    short_ad: PromoCopyBlock
    headlines: list[str]
    descriptions: list[str]
    telegram_posts: list[PromoSocialBlock]
    vk_posts: list[PromoSocialBlock]

    @field_validator("headlines", "descriptions")
    @classmethod
    def trim_lines(cls, value: list[str]) -> list[str]:
        items = []
        for item in value or []:
            text = str(item).strip()
            if text:
                items.append(text[:200])
        return items


class PromoSingleTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = ""
    body: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)

    @field_validator("headline", "body", "cta")
    @classmethod
    def trim_copy(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("hashtags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return CreativeSocialVariant.clean_tags(value)

    @field_validator("items")
    @classmethod
    def trim_items(cls, value: list[str]) -> list[str]:
        return [str(item).strip() for item in value or [] if str(item).strip()][:8]


class PromoSocialPostsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    posts: list[PromoSocialBlock] = Field(default_factory=list)


class PromoImageSpecPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str = ""
    format: str = "1:1"
    subject: str = ""
    audience: str = ""
    visualDirection: str = ""
    headline: str = ""
    cta: str = ""
    imagePrompt: str

    @field_validator(
        "concept",
        "format",
        "subject",
        "audience",
        "visualDirection",
        "headline",
        "cta",
        "imagePrompt",
    )
    @classmethod
    def trim_spec(cls, value: str) -> str:
        return (value or "").strip()


class PromoYandexPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)

    @field_validator("headlines", "descriptions")
    @classmethod
    def trim_yandex(cls, value: list[str]) -> list[str]:
        items = []
        for item in value or []:
            text = str(item).strip()
            if text:
                items.append(text[:200])
        return items[:8]


class PromoMetaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primaryTexts: list[str] = Field(default_factory=list)
    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)

    @field_validator("primaryTexts", "headlines", "descriptions")
    @classmethod
    def trim_meta(cls, value: list[str]) -> list[str]:
        items = []
        for item in value or []:
            text = str(item).strip()
            if text:
                items.append(text[:220])
        return items[:8]


class PromoTikTokPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hooks: list[str] = Field(default_factory=list)
    captions: list[str] = Field(default_factory=list)
    ctas: list[str] = Field(default_factory=list)

    @field_validator("hooks", "captions", "ctas")
    @classmethod
    def trim_tiktok(cls, value: list[str]) -> list[str]:
        items = []
        for item in value or []:
            text = str(item).strip()
            if text:
                items.append(text[:180])
        return items[:8]
