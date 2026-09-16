from __future__ import annotations

from app.common.enums import AccessPolicy, CommissionType, ConversionType
from app.core.exceptions import AppError
from app.modules.catalog import (
    is_valid_iso_country,
    normalize_traffic_source,
    parse_geo_codes,
    resolve_category_code,
)

HOLD_PERIOD_DAYS = (0, 3, 7, 14, 30)
ATTRIBUTION_PRESETS = (7, 14, 30, 60, 90)
OFFER_TEXT_MAX = 3000


def validate_offer_description(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        raise AppError("INVALID_DESCRIPTION", "Укажите описание оффера", 400)
    if len(text) > OFFER_TEXT_MAX:
        raise AppError("INVALID_DESCRIPTION", "Максимальная длина — 3000 символов", 400)
    return text


def normalize_partner_notes(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > OFFER_TEXT_MAX:
        raise AppError("INVALID_PARTNER_NOTES", "Максимальная длина — 3000 символов", 400)
    return text


def validate_access_policy(value: str | None) -> str:
    if value not in {item.value for item in AccessPolicy}:
        raise AppError("INVALID_ACCESS_POLICY", "Выберите политику доступа", 400)
    return value or AccessPolicy.OPEN.value


def validate_conversion_type(value: str | None) -> str:
    if value not in {item.value for item in ConversionType}:
        raise AppError("INVALID_CONVERSION_TYPE", "Выберите целевое действие", 400)
    return value or ConversionType.SALE.value


def validate_commission(commission_type: str | None, commission_value: float | None) -> tuple[str, float]:
    kind = commission_type or CommissionType.PERCENT.value
    if kind not in {item.value for item in CommissionType}:
        raise AppError("INVALID_COMMISSION_MODEL", "Выберите модель комиссии", 400)
    if commission_value is None:
        raise AppError("INVALID_COMMISSION_VALUE", "Укажите размер комиссии", 400)
    value = float(commission_value)
    if kind == CommissionType.PERCENT.value:
        if not (0 < value <= 100):
            raise AppError("INVALID_COMMISSION_VALUE", "Укажите размер комиссии", 400)
    elif value <= 0:
        raise AppError("INVALID_COMMISSION_VALUE", "Укажите размер комиссии", 400)
    return kind, value


def validate_hold_period_days(value: int | None) -> int:
    days = 0 if value is None else int(value)
    if days not in HOLD_PERIOD_DAYS:
        raise AppError("INVALID_HOLD_PERIOD", "Выберите холд-период", 400)
    return days


def validate_attribution_window_days(value: int | None) -> int:
    days = 30 if value is None else int(value)
    if days < 1 or days > 365:
        raise AppError("INVALID_ATTRIBUTION_WINDOW", "Укажите окно атрибуции", 400)
    return days


def validate_category_code(value: str | None, category_id: int | None = None) -> str:
    if category_id is not None and not value:
        raise AppError("INVALID_CATEGORY", "Выберите категорию", 400)
    code = resolve_category_code(value)
    if not code:
        raise AppError("INVALID_CATEGORY", "Выберите категорию", 400)
    return code


def validate_geo_codes(value) -> list[str]:
    codes = parse_geo_codes(value)
    if not codes:
        raise AppError("INVALID_GEO", "Выберите хотя бы одну страну", 400)
    for code in codes:
        if not is_valid_iso_country(code):
            raise AppError("INVALID_GEO", "Выберите хотя бы одну страну", 400)
    return codes


def validate_allowed_traffic(values: list[str] | None) -> list[str]:
    if not values:
        raise AppError("INVALID_TRAFFIC_SOURCES", "Выберите хотя бы один разрешённый источник трафика", 400)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        code = normalize_traffic_source(item)
        if not code:
            raise AppError("INVALID_TRAFFIC_SOURCES", "Выберите хотя бы один разрешённый источник трафика", 400)
        if code not in seen:
            seen.add(code)
            normalized.append(code)
    return normalized


def serialize_geo(codes: list[str]) -> str:
    return ",".join(codes)
