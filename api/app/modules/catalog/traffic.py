from __future__ import annotations

TRAFFIC_GROUPS = ("CONTENT", "PAID", "DIRECT", "SPECIAL", "OFFLINE")

TRAFFIC_SOURCES: list[tuple[str, str, str, str]] = [
    ("WEBSITE_CONTENT", "Сайты и блоги", "Websites and blogs", "CONTENT"),
    ("SEO", "SEO / поисковый органический трафик", "SEO / organic search", "CONTENT"),
    ("SOCIAL_ORGANIC", "Социальные сети", "Social networks", "CONTENT"),
    ("MESSENGERS", "Мессенджеры", "Messengers", "CONTENT"),
    ("VIDEO_CONTENT", "Видео-контент", "Video content", "CONTENT"),
    ("COMMUNITIES_FORUMS", "Форумы и сообщества", "Forums and communities", "CONTENT"),
    ("REVIEWS", "Обзоры и рейтинги", "Reviews and ratings", "CONTENT"),
    ("MEDIA_PUBLISHERS", "Онлайн-СМИ", "Online media", "CONTENT"),
    ("SEARCH_ADS", "Контекстная / поисковая реклама", "Search ads", "PAID"),
    ("SOCIAL_PAID", "Таргетированная реклама", "Targeted ads", "PAID"),
    ("DISPLAY_ADS", "Баннерная реклама", "Display ads", "PAID"),
    ("NATIVE_ADS", "Нативная реклама", "Native ads", "PAID"),
    ("TEASER_ADS", "Тизерная реклама", "Teaser ads", "PAID"),
    ("PROGRAMMATIC", "Programmatic", "Programmatic", "PAID"),
    ("VIDEO_ADS", "Видеореклама", "Video ads", "PAID"),
    ("IN_APP_ADS", "Реклама внутри приложений", "In-app ads", "PAID"),
    ("POP_TRAFFIC", "Pop / Popunder", "Pop / Popunder", "PAID"),
    ("REDIRECT_TRAFFIC", "Redirect-трафик", "Redirect traffic", "PAID"),
    ("INTERSTITIAL_ADS", "Interstitial", "Interstitial", "PAID"),
    ("EMAIL", "Email", "Email", "DIRECT"),
    ("SMS", "SMS", "SMS", "DIRECT"),
    ("WEB_PUSH", "Web Push", "Web Push", "DIRECT"),
    ("MOBILE_PUSH", "Mobile Push", "Mobile Push", "DIRECT"),
    ("CALL_CENTER", "Call-center / телемаркетинг", "Call-center / telemarketing", "DIRECT"),
    ("INFLUENCERS", "Блогеры / инфлюенсеры", "Bloggers / influencers", "SPECIAL"),
    ("COMPARISON_SITES", "Сайты сравнения", "Comparison sites", "SPECIAL"),
    ("SUB_AFFILIATE", "Субпартнёрские сети", "Sub-affiliate networks", "SPECIAL"),
    ("MOBILE_APPS", "Мобильные приложения", "Mobile apps", "SPECIAL"),
    ("BROWSER_EXTENSIONS", "Расширения браузера", "Browser extensions", "SPECIAL"),
    ("PERSONAL_REFERRAL", "Личные рекомендации", "Personal referrals", "SPECIAL"),
    ("OFFLINE_QR", "Офлайн / QR", "Offline / QR", "OFFLINE"),
    ("PRINT_MEDIA", "Печатные материалы", "Print materials", "OFFLINE"),
    ("OUTDOOR_ADVERTISING", "Наружная реклама", "Outdoor advertising", "OFFLINE"),
    ("EVENTS", "Мероприятия", "Events", "OFFLINE"),
    ("POS_OFFLINE", "Точки продаж", "Points of sale", "OFFLINE"),
]

LEGACY_TRAFFIC_MAP = {
    "seo": "SEO",
    "content": "WEBSITE_CONTENT",
    "social": "SOCIAL_ORGANIC",
    "youtube": "VIDEO_CONTENT",
    "telegram": "MESSENGERS",
    "email": "EMAIL",
    "ppc": "SEARCH_ADS",
}

_TRAFFIC_BY_CODE = {item[0]: item for item in TRAFFIC_SOURCES}


def traffic_codes() -> list[str]:
    return [item[0] for item in TRAFFIC_SOURCES]


def normalize_traffic_source(code: str | None) -> str | None:
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    if text in _TRAFFIC_BY_CODE:
        return text
    mapped = LEGACY_TRAFFIC_MAP.get(text)
    if mapped:
        return mapped
    upper = text.upper()
    if upper in _TRAFFIC_BY_CODE:
        return upper
    return LEGACY_TRAFFIC_MAP.get(text.lower())


def is_allowed_traffic_source(code: str | None) -> bool:
    return normalize_traffic_source(code) is not None
