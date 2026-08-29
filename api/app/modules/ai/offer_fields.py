CATEGORIES = ["SaaS", "Fintech", "Education", "E-commerce", "Marketing", "Other"]
GEO_OPTIONS = ["WW", "RU", "KZ", "BY", "UA", "US", "EU"]
TRAFFIC_TYPES = ["seo", "content", "social", "youtube", "telegram", "email", "ppc"]
CONVERSION_TYPES = ["sale", "signup", "lead", "application", "custom"]
ACCESS_POLICIES = ["open", "approval", "invite_only"]
COMMISSION_TYPES = ["percent", "fixed"]
CURRENCIES = ["RUB", "USD", "EUR"]

CONTENT_FIELDS = {
    "name",
    "description",
    "category",
    "geo",
    "partner_notes",
    "allowed_traffic",
    "forbidden_traffic",
    "product_url",
}
BUSINESS_RULE_FIELDS = {
    "conversion_type",
    "commission_type",
    "commission_value",
    "commission_currency",
    "attribution_window_days",
    "access_policy",
}
REWRITE_FIELDS = {"name", "description", "partner_notes"}
ALLOWED_PATCH_FIELDS = CONTENT_FIELDS | BUSINESS_RULE_FIELDS
TECHNICAL_FIELDS = {
    "id",
    "business_id",
    "product_id",
    "status",
    "created_at",
    "updated_at",
    "destination_url",
    "tracking_link_id",
    "short_code",
    "rqcid",
    "image_url",
    "visibility",
    "currency",
}

FIELD_LABELS = {
    "name": "Название",
    "description": "Описание",
    "category": "Категория",
    "geo": "GEO",
    "partner_notes": "Инструкции для партнёров",
    "allowed_traffic": "Разрешённый трафик",
    "forbidden_traffic": "Запрещённый трафик",
    "product_url": "Сайт продукта",
    "conversion_type": "Тип conversion goal",
    "commission_type": "Модель комиссии",
    "commission_value": "Размер комиссии",
    "commission_currency": "Валюта",
    "attribution_window_days": "Окно атрибуции",
    "access_policy": "Тип доступа",
}
