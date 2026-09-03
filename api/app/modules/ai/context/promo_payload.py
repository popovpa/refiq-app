from typing import Any

from app.modules.ai.context.offer_context import PURPOSE_CUSTOMER_ACQUISITION


def brief_user_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    product = snapshot.get("productContext") or {}
    return {
        "purpose": PURPOSE_CUSTOMER_ACQUISITION,
        "targetAudienceRole": "END_CUSTOMER",
        "promotedObject": "PRODUCT_OR_SERVICE",
        "materialPurpose": PURPOSE_CUSTOMER_ACQUISITION,
        "productContext": product,
        "affiliateConstraints": _compliance_constraints(snapshot),
        "brand": snapshot.get("brand") or {},
        "language": snapshot.get("language") or "ru",
        "constraints": snapshot.get("constraints") or {},
    }


def text_generation_payload(context: dict[str, Any], brief: dict[str, Any] | None, slot: str | None = None) -> dict[str, Any]:
    product = context.get("productContext") or {}
    brief = brief or {}
    payload: dict[str, Any] = {
        "purpose": PURPOSE_CUSTOMER_ACQUISITION,
        "audience": "END_CUSTOMER",
        "promotedObject": "PRODUCT_OR_SERVICE",
        "materialPurpose": PURPOSE_CUSTOMER_ACQUISITION,
        "productContext": product,
        "customerBenefits": brief.get("keyBenefits") or [],
        "verifiedClaims": brief.get("allowedClaims") or brief.get("verifiedProductFacts") or [],
        "callToAction": brief.get("cta") or "",
        "toneOfVoice": brief.get("toneOfVoice") or "",
        "visualDirection": brief.get("visualDirection") or "",
        "positioning": brief.get("positioning") or "",
        "prohibitedClaims": brief.get("prohibitedClaims") or [],
        "brief": _customer_brief(brief),
        "affiliateConstraints": _compliance_constraints(context),
        "constraints": context.get("constraints") or {},
        "language": context.get("language") or "ru",
        "brand": {
            "tone_of_voice": (context.get("brand") or {}).get("tone_of_voice"),
            "mandatory_disclaimers": (context.get("brand") or {}).get("mandatory_disclaimers") or [],
        },
    }
    if slot:
        payload["slot"] = slot
    if context.get("instruction"):
        payload["USER_GUIDANCE"] = {
            "trust": "UNTRUSTED",
            "source": "USER_GUIDANCE",
            "data": context["instruction"],
        }
        payload["instruction"] = context["instruction"]
    if context.get("channel"):
        payload["channel"] = context["channel"]
    return payload


def _customer_brief(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "purpose": PURPOSE_CUSTOMER_ACQUISITION,
        "targetAudience": brief.get("targetAudience") or "",
        "promotedProduct": brief.get("promotedProduct") or "",
        "primaryCustomerNeed": brief.get("primaryCustomerNeed") or "",
        "mainValueProposition": brief.get("mainValueProposition") or "",
        "customerBenefits": brief.get("keyBenefits") or [],
        "verifiedProductFacts": brief.get("verifiedProductFacts") or [],
        "allowedClaims": brief.get("allowedClaims") or [],
        "prohibitedClaims": brief.get("prohibitedClaims") or [],
        "toneOfVoice": brief.get("toneOfVoice") or "",
        "visualDirection": brief.get("visualDirection") or "",
        "creativeConcepts": brief.get("creativeConcepts") or [],
        "customerCTA": brief.get("cta") or "",
        "positioning": brief.get("positioning") or "",
    }


def _compliance_constraints(snapshot: dict[str, Any]) -> dict[str, Any]:
    affiliate = snapshot.get("affiliateConstraints") or {}
    return {
        "internalOnly": True,
        "mustNotAppearInCustomerCreative": True,
        "useAsComplianceOnly": True,
        "forbiddenTraffic": affiliate.get("forbiddenTraffic") or [],
        "allowedTraffic": affiliate.get("allowedTraffic") or [],
        "partnerNotes": affiliate.get("partnerNotes") or "",
    }
