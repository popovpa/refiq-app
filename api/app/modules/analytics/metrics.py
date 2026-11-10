"""Single definition of analytics metrics.

Counts and rates on every tab must use these helpers.

Clicks
    Registered tracker clicks in PostgreSQL.

Conversions and CR
    Default statuses are pending, approved and paid.
    Rejected and reversed stay out of CR unless the request lists statuses explicitly.
    CR is conversions / clicks × 100. A zero click denominator is null.

Commission and EPC
    Default commission is the sum of partner commission_amount on approved and paid
    conversions. Rows without partner_id are business-owned promotion and are excluded.
    An explicit status list applies to both the conversion count and the commission sum.
    EPC is that commission divided by clicks. A zero click denominator is null.
    ROI is never calculated: media spend is not collected.

Behavior
    Missing SDK events are not zeros and are not bounces.
    Bounce and engagement use only sessions that actually have a measurement.
    Coverage below 50% is partial. No measurements is unavailable.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

Quality = Literal["reliable", "partial", "unavailable"]

COUNT_STATUSES = ("pending", "approved", "paid")
COMMISSION_STATUSES = ("approved", "paid")
CONFIRMED_STATUSES = ("approved", "paid")
PENDING_STATUSES = ("pending",)
REJECTED_STATUSES = ("rejected", "reversed")

PARTIAL_COVERAGE = Decimal("0.50")
MAX_VITAL_MS = 600_000
MAX_CLS = Decimal("10")
MAX_WEIGHT_BYTES = 500_000_000
MAX_RQCID_INTERSECTION = 8000
MAX_TABLE_ROWS = 20
MAX_CHART_GROUPS = 8
MONEY = Decimal("0.01")
RATE = Decimal("0.01")
CHANGE = Decimal("0.1")


def decimal_or_none(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    parsed = decimal_or_none(value)
    if parsed is None:
        return Decimal("0.00")
    return parsed.quantize(MONEY)


def quant_rate(value: Decimal) -> Decimal:
    return value.quantize(RATE)


def as_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def ratio(numerator: int | Decimal | None, denominator: int | Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None:
        return None
    denom = Decimal(denominator)
    if denom <= 0:
        return None
    return quant_rate(Decimal(numerator) / denom * Decimal(100))


def epc(commission: Decimal | None, clicks: int | None) -> Decimal | None:
    if commission is None or clicks is None or clicks <= 0:
        return None
    return (commission / Decimal(clicks)).quantize(MONEY)


def change_pct(current: Decimal | int | None, previous: Decimal | int | None) -> Decimal | None:
    if current is None or previous is None:
        return None
    prev = Decimal(previous)
    if prev == 0:
        return None
    return ((Decimal(current) - prev) / prev * Decimal(100)).quantize(CHANGE)


def coverage_quality(observed: int, total: int) -> Quality:
    if total <= 0 or observed <= 0:
        return "unavailable"
    if Decimal(observed) / Decimal(total) < PARTIAL_COVERAGE:
        return "partial"
    return "reliable"


def postgres_click_policy(
    *,
    needs_intersection: bool,
    clickhouse_ok: bool,
    rqcid_count: int | None,
    truncated: bool,
) -> str:
    """How registered clicks may be filtered by a behavioral constraint.

    all — no behavioral filter, PostgreSQL is authoritative.
    subset — exact rqcid intersection.
    none — the filter matches no clicks.
    unavailable — the filter cannot be applied safely.
    """

    if not needs_intersection:
        return "all"
    if not clickhouse_ok or truncated or rqcid_count is None:
        return "unavailable"
    if rqcid_count == 0:
        return "none"
    if rqcid_count > MAX_RQCID_INTERSECTION:
        return "unavailable"
    return "subset"


DEFINITIONS = {
    "clicks": "Зарегистрированные клики трекера.",
    "conversions": "Бизнес-конверсии. По умолчанию статусы pending, approved и paid.",
    "cr": "Конверсии / клики × 100. При нуле кликов значение отсутствует.",
    "commission": "Комиссия партнёра. По умолчанию статусы approved и paid. Собственное продвижение бизнеса не создаёт комиссию.",
    "epc": "Подтверждённая партнёрская комиссия / клики.",
    "reached": "Уникальные rqcid кликов, у которых в ClickHouse есть page_view.",
    "engagement": "Доля сессий с подтверждённым взаимодействием среди сессий, по которым измерение есть.",
    "bounce": "Доля измеренных сессий без клика, прокрутки и активного времени. Сессии без page_engagement в знаменатель не входят.",
    "duration": "Средняя активная длительность сессий, где page_engagement больше нуля.",
    "pages_per_session": "Уникальные page_view / уникальные сессии SDK.",
    "scroll": "Доля просмотров с событием scroll, достигших порога. Знаменатель — просмотры с наблюдением прокрутки.",
    "source": "Источник клика: traffic_source ссылки, иначе домен referer, иначе прямой заход.",
    "roi": "Не рассчитывается: расходы на медиабаинг не собираются.",
    "target_action": "Браузерное целевое действие в оффере не настроено и не подменяется form_submit.",
    "lcp": "P75 web_vital_lcp по событиям page_performance, одно измерение на page_view.",
    "inp": "P75 web_vital_inp. Без валидных измерений метрика недоступна.",
    "cls": "P75 web_vital_cls по валидным измерениям.",
    "weight": "P75 размера загрузки: performance_transfer_size, иначе resource_transfer_bytes.",
    "load_errors": "Доля просмотров с resource_failed_count > 0 среди просмотров, где счётчик ресурсов заполнен.",
}
