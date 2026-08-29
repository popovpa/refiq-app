from typing import Any

from app.modules.ai.offer_fields import (
    ACCESS_POLICIES,
    CATEGORIES,
    COMMISSION_TYPES,
    CONVERSION_TYPES,
    CURRENCIES,
    GEO_OPTIONS,
    TRAFFIC_TYPES,
)


def _str_enum(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": values}


def _string_array(values: list[str]) -> dict[str, Any]:
    return {"type": "array", "items": _str_enum(values)}


def offer_draft_schema() -> dict[str, Any]:
    draft = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "category": _str_enum(CATEGORIES),
            "geo": _str_enum(GEO_OPTIONS),
            "partner_notes": {"type": "string"},
            "allowed_traffic": _string_array(TRAFFIC_TYPES),
            "forbidden_traffic": _string_array(TRAFFIC_TYPES),
            "product_url": {"type": "string"},
        },
        "required": [
            "name",
            "description",
            "category",
            "geo",
            "partner_notes",
            "allowed_traffic",
            "forbidden_traffic",
            "product_url",
        ],
    }
    recommendations = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "conversion_type": _str_enum(CONVERSION_TYPES),
            "commission_type": _str_enum(COMMISSION_TYPES),
            "commission_value": {"type": "number"},
            "commission_currency": _str_enum(CURRENCIES),
            "attribution_window_days": {"type": "integer"},
            "access_policy": _str_enum(ACCESS_POLICIES),
        },
        "required": [
            "conversion_type",
            "commission_type",
            "commission_value",
            "commission_currency",
            "attribution_window_days",
            "access_policy",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"draft": draft, "recommendations": recommendations},
        "required": ["draft", "recommendations"],
    }


def offer_edit_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": [
                                "name",
                                "description",
                                "category",
                                "geo",
                                "partner_notes",
                                "allowed_traffic",
                                "forbidden_traffic",
                                "product_url",
                                "conversion_type",
                                "commission_type",
                                "commission_value",
                                "commission_currency",
                                "attribution_window_days",
                                "access_policy",
                            ],
                        },
                        "new_value": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["field", "new_value", "reason"],
                },
            }
        },
        "required": ["changes"],
    }


def offer_rewrite_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }


def _variant_base() -> dict[str, Any]:
    return {
        "kind": {"type": "string", "enum": ["short", "expert", "promotional"]},
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "cta": {"type": "string"},
    }


def creative_text_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": _variant_base(),
                    "required": ["kind", "headline", "body", "cta"],
                },
            }
        },
        "required": ["variants"],
    }


def creative_social_schema() -> dict[str, Any]:
    properties = {**_variant_base(), "hashtags": {"type": "array", "items": {"type": "string"}}}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": properties,
                    "required": ["kind", "headline", "body", "cta", "hashtags"],
                },
            }
        },
        "required": ["variants"],
    }


def creative_rewrite_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "body", "cta", "hashtags"],
    }


def _copy_block() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
        },
        "required": ["headline", "body", "cta"],
    }


def _social_block() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "body", "cta", "hashtags"],
    }


def promo_brief_schema() -> dict[str, Any]:
    properties = {
        "purpose": {"type": "string"},
        "promotedProduct": {"type": "string"},
        "primaryCustomerNeed": {"type": "string"},
        "targetAudience": {"type": "string"},
        "mainValueProposition": {"type": "string"},
        "keyBenefits": {"type": "array", "items": {"type": "string"}},
        "verifiedProductFacts": {"type": "array", "items": {"type": "string"}},
        "toneOfVoice": {"type": "string"},
        "cta": {"type": "string"},
        "restrictions": {"type": "array", "items": {"type": "string"}},
        "creativeConcepts": {"type": "array", "items": {"type": "string"}},
        "positioning": {"type": "string"},
        "allowedClaims": {"type": "array", "items": {"type": "string"}},
        "prohibitedClaims": {"type": "array", "items": {"type": "string"}},
        "visualDirection": {"type": "string"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def promo_kit_texts_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "universal_ad": _copy_block(),
            "short_ad": _copy_block(),
            "headlines": {"type": "array", "items": {"type": "string"}},
            "descriptions": {"type": "array", "items": {"type": "string"}},
            "telegram_posts": {"type": "array", "items": _social_block()},
            "vk_posts": {"type": "array", "items": _social_block()},
        },
        "required": [
            "universal_ad",
            "short_ad",
            "headlines",
            "descriptions",
            "telegram_posts",
            "vk_posts",
        ],
    }


def promo_single_text_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headline", "body", "cta", "hashtags", "items"],
    }


def promo_social_posts_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "posts": {"type": "array", "items": _social_block()},
        },
        "required": ["posts"],
    }


def promo_image_spec_schema() -> dict[str, Any]:
    properties = {
        "concept": {"type": "string"},
        "format": {"type": "string"},
        "subject": {"type": "string"},
        "audience": {"type": "string"},
        "visualDirection": {"type": "string"},
        "headline": {"type": "string"},
        "cta": {"type": "string"},
        "imagePrompt": {"type": "string"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def promo_yandex_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headlines": {"type": "array", "items": {"type": "string"}},
            "descriptions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["headlines", "descriptions"],
    }


def promo_meta_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "primaryTexts": {"type": "array", "items": {"type": "string"}},
            "headlines": {"type": "array", "items": {"type": "string"}},
            "descriptions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["primaryTexts", "headlines", "descriptions"],
    }


def promo_tiktok_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "hooks": {"type": "array", "items": {"type": "string"}},
            "captions": {"type": "array", "items": {"type": "string"}},
            "ctas": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["hooks", "captions", "ctas"],
    }
