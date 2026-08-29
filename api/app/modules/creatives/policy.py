from app.common.enums import CreativePolicyStatus
from app.modules.brand_kits.models import BrandKit
from app.modules.offers.models import Offer

MAX_HEADLINE = 120
MAX_BODY = 2000
MAX_CTA = 80
FORBIDDEN_TRACKING = ("rqcid", "short_code", "shortcode", "trackinglinkid")


class CreativePolicyValidator:
    def validate_text(
        self,
        content: dict,
        *,
        offer: Offer,
        brand_kit: BrandKit | None = None,
        require_cta: bool = False,
    ) -> dict:
        issues: list[dict] = []
        headline = str(content.get("headline") or "")
        body = str(content.get("body") or "")
        cta = str(content.get("cta") or "")
        blob = " ".join([headline, body, cta, " ".join(content.get("hashtags") or [])]).lower()

        if len(headline) > MAX_HEADLINE:
            issues.append(_issue("HEADLINE_TOO_LONG", "warning", "Заголовок слишком длинный"))
        if len(body) > MAX_BODY:
            issues.append(_issue("BODY_TOO_LONG", "blocked", "Текст превышает допустимую длину"))
        if len(cta) > MAX_CTA:
            issues.append(_issue("CTA_TOO_LONG", "warning", "Призыв к действию слишком длинный"))
        if require_cta and not cta.strip():
            issues.append(_issue("CTA_REQUIRED", "warning", "Нет призыва к действию"))

        for token in FORBIDDEN_TRACKING:
            if token in blob:
                issues.append(_issue("TRACKING_ID_FORBIDDEN", "blocked", "Нельзя использовать tracking ID или rqcid"))
                break

        forbidden = list(brand_kit.forbidden_claims or []) if brand_kit else []
        for claim in forbidden:
            text = str(claim).strip()
            if text and text.lower() in blob:
                issues.append(_issue("FORBIDDEN_CLAIM", "blocked", "Использовано запрещённое утверждение"))

        disclaimers = list(brand_kit.mandatory_disclaimers or []) if brand_kit else []
        for line in disclaimers:
            text = str(line).strip()
            if text and text.lower() not in blob:
                issues.append(_issue("DISCLAIMER_MISSING", "blocked", "Нет обязательного дисклеймера"))

        notes = (offer.partner_notes or "").strip()
        if notes and "без гарант" in notes.lower() and "гарант" in blob:
            issues.append(_issue("OFFER_RESTRICTION", "warning", "Формулировка может нарушать ограничения оффера"))

        status = CreativePolicyStatus.VALID.value
        if any(item["severity"] == "blocked" for item in issues):
            status = CreativePolicyStatus.BLOCKED.value
        elif issues:
            status = CreativePolicyStatus.WARNING.value
        return {"status": status, "issues": issues}


def _issue(code: str, severity: str, message: str) -> dict:
    return {"code": code, "severity": severity, "message": message}
