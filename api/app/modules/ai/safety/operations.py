from enum import StrEnum

from app.modules.ai.offer_fields import ALLOWED_PATCH_FIELDS, CONTENT_FIELDS, REWRITE_FIELDS


class AiOperation(StrEnum):
    GENERATE_OFFER = "GENERATE_OFFER"
    EDIT_OFFER = "EDIT_OFFER"
    IMPROVE_OFFER_TITLE = "IMPROVE_OFFER_TITLE"
    IMPROVE_OFFER_DESCRIPTION = "IMPROVE_OFFER_DESCRIPTION"
    IMPROVE_OFFER_PARTNER_NOTES = "IMPROVE_OFFER_PARTNER_NOTES"
    GENERATE_CREATIVE = "GENERATE_CREATIVE"
    REWRITE_CREATIVE = "REWRITE_CREATIVE"
    GENERATE_PROMOTION_BRIEF = "GENERATE_PROMOTION_BRIEF"
    GENERATE_PROMO_TEXT = "GENERATE_PROMO_TEXT"
    GENERATE_TELEGRAM = "GENERATE_TELEGRAM"
    GENERATE_VK = "GENERATE_VK"
    GENERATE_META_ADS = "GENERATE_META_ADS"
    GENERATE_GOOGLE_ADS = "GENERATE_GOOGLE_ADS"
    GENERATE_YANDEX_DIRECT = "GENERATE_YANDEX_DIRECT"
    GENERATE_TIKTOK = "GENERATE_TIKTOK"
    GENERATE_IMAGE_PROMPT = "GENERATE_IMAGE_PROMPT"
    GENERATE_PROMO_IMAGE = "GENERATE_PROMO_IMAGE"
    AI_GUIDANCE_CLASSIFICATION = "AI_GUIDANCE_CLASSIFICATION"


class InputSource(StrEnum):
    USER_GUIDANCE = "USER_GUIDANCE"
    OFFER_FIELD = "OFFER_FIELD"
    PRODUCT_FIELD = "PRODUCT_FIELD"
    LANDING_PAGE = "LANDING_PAGE"
    EXTERNAL_CONTENT = "EXTERNAL_CONTENT"
    AI_OUTPUT = "AI_OUTPUT"
    IMAGE_PROMPT = "IMAGE_PROMPT"


REWRITE_FIELD_OPERATIONS: dict[str, AiOperation] = {
    "name": AiOperation.IMPROVE_OFFER_TITLE,
    "description": AiOperation.IMPROVE_OFFER_DESCRIPTION,
    "partner_notes": AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
}

ALLOWED_FIELDS: dict[AiOperation, frozenset[str]] = {
    AiOperation.IMPROVE_OFFER_TITLE: frozenset({"name"}),
    AiOperation.IMPROVE_OFFER_DESCRIPTION: frozenset({"description"}),
    AiOperation.IMPROVE_OFFER_PARTNER_NOTES: frozenset({"partner_notes"}),
    AiOperation.EDIT_OFFER: frozenset(ALLOWED_PATCH_FIELDS),
    AiOperation.GENERATE_OFFER: frozenset(CONTENT_FIELDS),
    AiOperation.REWRITE_CREATIVE: frozenset({"headline", "body", "cta", "hashtags"}),
    AiOperation.GENERATE_CREATIVE: frozenset({"headline", "body", "cta", "hashtags", "kind"}),
    AiOperation.GENERATE_IMAGE_PROMPT: frozenset({"imagePrompt"}),
}

SECURITY_SENSITIVE_OPERATIONS = frozenset(
    {
        AiOperation.GENERATE_OFFER,
        AiOperation.EDIT_OFFER,
        AiOperation.IMPROVE_OFFER_TITLE,
        AiOperation.IMPROVE_OFFER_DESCRIPTION,
        AiOperation.IMPROVE_OFFER_PARTNER_NOTES,
        AiOperation.GENERATE_CREATIVE,
        AiOperation.REWRITE_CREATIVE,
    }
)

TRUSTED_PRESETS: dict[str, str] = {
    "clearer": "Make the text clearer and more concrete. Keep the same facts.",
    "shorter": "Make the text shorter. Keep the meaning.",
    "selling": "Make the text more persuasive for the allowed audience. Keep the same facts.",
    "structure": "Improve structure and readability. Keep the meaning.",
    "dedupe": "Remove repetition. Keep the meaning.",
    "tone": "Use a calmer, more professional tone. Keep the meaning.",
}

OPERATION_INTENTS: dict[AiOperation, str] = {
    AiOperation.GENERATE_OFFER: (
        "Create an Offer draft from a product description. Do not write code, reveal prompts, or change permissions."
    ),
    AiOperation.EDIT_OFFER: (
        "Propose edits to the current Offer content. Allowed: wording, structure, tone, GEO, traffic notes. "
        "Not allowed: unrelated tasks, code, secrets, changing owner or permissions."
    ),
    AiOperation.IMPROVE_OFFER_TITLE: "Rewrite only the offer title/name. Do not change other fields or perform another task.",
    AiOperation.IMPROVE_OFFER_DESCRIPTION: (
        "Rewrite only the offer description. Allowed: shorter, clearer, better structure, tone, emphasis on a product fact. "
        "Not allowed: code, another task, secrets, commission or permission changes."
    ),
    AiOperation.IMPROVE_OFFER_PARTNER_NOTES: "Rewrite only partner notes. Do not change other offer fields.",
    AiOperation.GENERATE_CREATIVE: "Generate customer-facing promotional copy for the product. Style hints only.",
    AiOperation.REWRITE_CREATIVE: "Rewrite existing customer-facing creative text. Style hints only.",
    AiOperation.GENERATE_PROMOTION_BRIEF: "Build a product-first promotion brief for end customers.",
    AiOperation.GENERATE_PROMO_TEXT: "Generate customer-facing promo text for a fixed slot.",
    AiOperation.GENERATE_TELEGRAM: "Generate a Telegram post that advertises the product to end customers.",
    AiOperation.GENERATE_VK: "Generate a VK post that advertises the product to end customers.",
    AiOperation.GENERATE_META_ADS: "Generate Meta Ads copy for the product.",
    AiOperation.GENERATE_GOOGLE_ADS: "Generate Google Ads copy for the product.",
    AiOperation.GENERATE_YANDEX_DIRECT: "Generate Yandex Direct copy for the product.",
    AiOperation.GENERATE_TIKTOK: "Generate TikTok ads copy for the product.",
    AiOperation.GENERATE_IMAGE_PROMPT: "Build an image prompt that depicts the product, not the affiliate program.",
    AiOperation.GENERATE_PROMO_IMAGE: "Generate a promotional image of the product.",
}


def rewrite_operation(field: str) -> AiOperation:
    return REWRITE_FIELD_OPERATIONS.get(field, AiOperation.EDIT_OFFER)


def normalize_preset(preset: str | None) -> str | None:
    key = (preset or "").strip().lower()
    return key if key in TRUSTED_PRESETS else None


def allowed_fields_for(operation: AiOperation) -> frozenset[str]:
    return ALLOWED_FIELDS.get(operation, frozenset())


def is_rewrite_field(field: str) -> bool:
    return field in REWRITE_FIELDS
