from app.modules.ai.application.creative.promo_copy_guard import looks_like_affiliate_recruiting

BRIEF_V1 = "promo-brief-v3"
KIT_TEXT_V1 = "promo-kit-text-v3"
SINGLE_TEXT_V1 = "promo-single-text-v3"
IMAGE_V1 = "promo-image-v4"
IMAGE_SPEC_V1 = "promo-image-spec-v2"

_CUSTOMER_ACQUISITION = """
PURPOSE is CUSTOMER_ACQUISITION.
AUDIENCE is the END CUSTOMER who may purchase or use the product/service.
PROMOTED OBJECT is the PRODUCT or SERVICE in PRODUCT_CONTEXT — never the Offer entity, never the affiliate program.

Create advertising for the end product or service described in PRODUCT_CONTEXT.
Do NOT advertise the affiliate program, referral program, partnership opportunity, or the Offer entity itself.
Do NOT mention or visually represent partner commissions, payouts, CPA/CPS/CPL, affiliate rewards, webmaster earnings, attribution rules, traffic-source rules, or internal promotional conditions.
Affiliate information is internal context only and must never appear in the customer-facing creative.

The main subject must be the promoted product/service (the car, the medical service, the SaaS product, etc.).
Do not use affiliate mechanics as the creative concept.

Forbidden in customer-facing output (semantic, not only exact strings):
partner program recruiting, «Партнёрская программа» unless that is the sold product itself,
«Партнёр» / webmaster as the audience, referral earnings, «Получайте комиссию»,
«Заработайте X ₽», «X ₽ за продажу», payout terms, CPA/CPS/CPL, attribution,
allowed/forbidden traffic sources, promotion instructions, RefIQ, internal IDs.

Allowed: verified product name, brand, real specs, real customer benefits,
confirmed price/discount/GEO/address/CTA from PRODUCT_CONTEXT only.

If PRODUCT_CONTEXT.contextLimited is true, stay generic and use only named facts.
Do not fill missing product information with partner commission, conversion rules, or traffic terms.
Do not invent price, discount, free shipping, warranty, specs, promotions, medical/financial claims, deadlines, or availability.
"""

_SHARED = f"""
You write customer-facing promotional materials that advertise a product or service to end customers.
Return only structured JSON that matches the provided schema.
Use only facts present in PRODUCT_CONTEXT and the Promotion Brief.
{_CUSTOMER_ACQUISITION}
Do not invent product price, discounts, guarantees, product specs, legal claims, or terms that are not in PRODUCT_CONTEXT.
Do not generate tracking IDs, short codes, tracking parameters, destination URLs for tracking, or rqcid.
Do not mention RefIQ internals.
Keep the language requested in the context (usually Russian).
AffiliateConstraints may be used only as compliance constraints (channels to avoid encouraging). Never quote them in the ad.
"""


def brief_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {BRIEF_V1}
Build an internal product-first Promotion Brief for CUSTOMER_ACQUISITION.
purpose: always CUSTOMER_ACQUISITION.
targetAudience: end customers for this product/service (GEO/category/description), never partners or webmasters.
promotedProduct: the product/service name from PRODUCT_CONTEXT.
primaryCustomerNeed: the customer problem the product solves, from facts only.
mainValueProposition: one sentence of customer value from the product description.
keyBenefits: 3-5 customer benefits taken from PRODUCT_CONTEXT, not invented, never partner earnings.
verifiedProductFacts: short facts copied from PRODUCT_CONTEXT only.
toneOfVoice: professional, clear, not clickbait.
cta: a short customer CTA (learn more, book, buy, request) matching customerAction. Never a partner CTA.
restrictions: compliance notes derived from affiliateConstraints and brand forbidden claims. Do not turn them into ad copy.
creativeConcepts: 2-3 visual/copy directions about the PRODUCT for end customers.
Never propose concepts like «партнёрская программа», earning on referrals, or commission for a sale.
positioning: how the product should be framed vs alternatives, from facts only.
allowedClaims: phrases supported by PRODUCT_CONTEXT.
prohibitedClaims: discounts, prices, guarantees, invented specs, affiliate recruiting, commission, and anything forbidden.
visualDirection: consistent campaign look for all images in this run, with the product/service as the primary subject.
"""


def kit_texts_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {KIT_TEXT_V1}
Write a coordinated customer-facing promotion kit for the PRODUCT, not the Offer.
universal_ad: a complete ad with headline, body, customer cta.
short_ad: a shorter version of the same customer message.
headlines: exactly 5 alternative product headlines.
descriptions: exactly 3 short product descriptions.
telegram_posts: 3 Telegram posts that advertise the product to end customers.
vk_posts: 3 VK posts in the same customer-facing style.
If a Meta/Facebook or Instagram slot is requested, advertise the product to end customers the same way.
Do not write partner-recruiting copy in any slot.
Do not append a tracking link; the partner will add their own.
"""


def single_text_system_prompt(slot: str) -> str:
    return f"""{_SHARED}
Prompt version: {SINGLE_TEXT_V1}
Write advertising content for an end customer considering the PRODUCT.
Regenerate only this customer-facing material: {slot}.
Do not describe how partners promote this Offer.
Do not mention partner rewards or affiliate economics.
Use Offer restrictions only as compliance constraints.
Keep the same language, facts, and brief.
For headlines, put the lines in items (5 items) and also join them in body.
For descriptions, put 3 items and join them in body.
For a single ad, fill headline, body, and cta.
For a social post, also fill hashtags (3 or fewer, no #).
"""


YANDEX_V1 = "promo-yandex-direct-v3"


def yandex_direct_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {YANDEX_V1}
Write Yandex Direct text ads that advertise the PRODUCT to end customers, not generic marketing copy and not partner recruiting.
headlines: exactly 5 alternative titles, each at most 56 characters, specific to this product/service.
descriptions: exactly 5 alternative ad texts, each at most 81 characters.
Sound like search ads: concrete, scannable, no clickbait.
Use only facts from PRODUCT_CONTEXT and the Promotion Brief.
Do not invent discounts, prices, guarantees, ratings, limited-time deals, or product properties.
Respect prohibitedClaims. Use forbidden traffic notes only as compliance, never as ad text.
Do not include tracking links, URLs, or rqcid.
"""


GOOGLE_V1 = "promo-google-ads-v1"


def google_ads_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {GOOGLE_V1}
Write Google Ads Responsive Search Ad copy that advertises the PRODUCT to end customers.
headlines: exactly 5 alternative titles, each at most 30 characters.
descriptions: exactly 4 alternative descriptions, each at most 90 characters.
Do not reuse a Yandex Direct voice. Sound like Google search ads.
Use only facts from PRODUCT_CONTEXT and the Promotion Brief.
Do not invent discounts, prices, guarantees, ratings, or product properties.
Do not write partner-recruiting copy or tracking links.
"""


META_V1 = "promo-meta-ads-v1"


def meta_ads_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {META_V1}
Write a Meta Ads (Facebook/Instagram) kit that advertises the PRODUCT to end customers.
primaryTexts: exactly 3 feed primary texts.
headlines: exactly 5 short headlines.
descriptions: exactly 3 short link descriptions.
Do not write partner-recruiting copy or tracking links.
Use only facts from PRODUCT_CONTEXT and the Promotion Brief.
"""


TIKTOK_V1 = "promo-tiktok-ads-v1"


def tiktok_ads_system_prompt() -> str:
    return f"""{_SHARED}
Prompt version: {TIKTOK_V1}
Write TikTok Ads text assets for short performance content about the PRODUCT for end customers.
hooks: exactly 3 short opening hooks.
captions: exactly 3 captions / primary texts.
ctas: exactly 3 customer CTA variants.
Do not generate a video, script, or storyboard.
Do not write partner-recruiting copy or tracking links.
Use only facts from PRODUCT_CONTEXT and the Promotion Brief.
"""


def social_posts_system_prompt(slot: str) -> str:
    if "telegram" in slot:
        channel = "Telegram"
        extra = (
            "Create 3 ready-to-publish Telegram posts: short, informative, and more native. "
            "Paragraphs, lists, a natural customer CTA, and moderate emoji are allowed if the tone allows."
        )
    elif "vk" in slot:
        channel = "VK Реклама"
        extra = (
            "Create 3 VK advertising variants with a main text, headline, and customer CTA. "
            "This is paid VK promotion copy, not a community diary post."
        )
    elif "instagram" in slot or "meta" in slot or "facebook" in slot:
        channel = "Meta/Facebook"
        extra = "Create 3 coordinated Meta placements that advertise the product."
    else:
        channel = slot
        extra = "Create 3 coordinated posts."
    return f"""{_SHARED}
Prompt version: {SINGLE_TEXT_V1}
Write 3 coordinated {channel} posts that advertise the PRODUCT to end customers.
{extra}
Keep the campaign voice identical to other materials in this run.
posts: 3 items with headline, body, customer cta, optional hashtags without #.
Do not write partner-recruiting copy.
Do not append a tracking link.
"""


def image_spec_system_prompt(*, qr_safe: bool = False, compact: bool = False) -> str:
    qr = ""
    if qr_safe:
        qr = """
Leave a quiet empty rectangle in the bottom-right 22% of the canvas for a QR that software will add later.
Do not describe a QR code, barcode, URL, button, or tracking mark in the image.
"""
    rewrite = ""
    if compact:
        rewrite = """
REWRITE the previous imagePrompt. Remove any affiliate, commission, payout, or partner-program language.
Remove every CTA button, UI button, link, URL, and action label from the scene.
Keep the product name as the main subject and the visual style from the offer description. Do not shorten for a character cap.
"""
    return f"""{_SHARED}
Prompt version: {IMAGE_SPEC_V1}
Write a complete visual specification for a customer-facing product advertisement.
The image model will render ONLY imagePrompt. It must not receive Offer, commission, or affiliate rules.
Ground the scene in the offer description field (`description` / PRODUCT_CONTEXT.description).
Include that description as facts about the promoted product/service.
imagePrompt must:
- advertise the PRODUCT/SERVICE to an end customer;
- depict what the offer description says the product or service is;
- name the real product as the main visual subject;
- be a photographic or illustrated product scene, not a landing-page mockup;
- contain NO CTA buttons, UI buttons, app-store badges, forms, phone/email chips, or clickable-looking controls;
- contain NO URLs, short links, QR codes, barcodes, or other action links;
- allow at most the product name as simple typography, never as a button or hyperlink;
- be a full visual prompt with no character cap;
- never mention commission, payout, CPA/CPS, partner program, webmaster, traffic rules, or RefIQ.
Do not invent prices, discounts, medical or financial claims, or addresses.
{rewrite}
{qr}
"""


def image_prompt(
    context: dict,
    brief: dict,
    concept: str,
    *,
    aspect: str = "1:1",
    qr_safe: bool = False,
) -> str:
    product = context.get("productContext") or context.get("offer") or {}
    brand = context.get("brand") or {}
    colors = ", ".join(brand.get("colors") or []) or "deep green and white"
    facts = product.get("verifiedFacts") or []
    fact_lines = "\n".join(f"- {item}" for item in facts) or "- (none beyond the product name)"
    benefits = brief.get("keyBenefits") or []
    benefit_lines = "\n".join(f"- {item}" for item in benefits) or "- (only what PRODUCT_CONTEXT supports)"
    extra = (concept or "").strip()
    if _affiliate_concept(extra):
        extra = ""
    extra = extra or (brief.get("mainValueProposition") or product.get("name") or "")
    visual = brief.get("visualDirection") or extra
    description = (product.get("description") or "").strip()
    limited = "yes" if product.get("contextLimited") else "no"
    forbidden = context.get("restrictions") or []
    restriction_lines = "\n".join(f"- {item}" for item in forbidden) or "- (none beyond the strict rules below)"
    qr_block = ""
    if qr_safe:
        qr_block = """
QR LAYOUT:
Leave a quiet empty rectangle in the bottom-right 22% of the canvas for a QR code that software will add later.
Do not draw any QR code, barcode, URL, tracking code, button, or fake scannable pattern.
Keep the main subject out of that bottom-right zone.
Never write «QR партнёра», «Партнёрская ссылка», or commission copy.
"""
    return f"""PURPOSE:
Customer acquisition.

AUDIENCE:
End customers interested in the promoted product/service.

PRODUCT:
Name: {product.get("name") or ""}
Description: {description}
Category: {product.get("category") or ""}
GEO: {product.get("geo") or ""}
Context limited: {limited}

CUSTOMER VALUE:
{brief.get("mainValueProposition") or extra}
{benefit_lines}

VERIFIED FACTS:
{fact_lines}

VISUAL DIRECTION:
{visual}
Brand colors: {colors}
Creative concept: {extra}
The main visual subject must be the promoted product/service described above.
Build the scene from the product description, not from a marketing CTA.

RESTRICTIONS:
{restriction_lines}
If Context limited is yes, stay generic and use only named facts. Do not invent a story from partner economics.

STRICT RULES:
- Advertise the product/service, not the affiliate offer.
- Never mention partner commission, payout, CPA/CPS, or earning opportunities.
- Never show traffic-source or payout rules.
- Never invent facts.
- The product/service must be the primary subject of the creative.
- Do not depict fake reviews, guaranteed results, prices, or discounts unless they appear in VERIFIED FACTS.
- No CTA buttons, UI buttons, app-store badges, forms, or clickable-looking controls.
- No action links, URLs, short links, phone/email chips, or “learn more / buy / sign up” labels on the image.
- Visible text, if any, may be only the product name as plain typography — never a button.
- No watermarks. No QR codes. No tracking codes. No rqcid.
Prompt version: {IMAGE_V1}
Create a {aspect} promotional image of this product/service.
{qr_block}
"""


def _affiliate_concept(text: str) -> bool:
    return looks_like_affiliate_recruiting(text or "")
