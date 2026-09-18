from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from app.common.enums import SupportedCurrency
from app.modules.finance.errors import fin_error

MONEY_QUANT = Decimal("0.01")
RUB = SupportedCurrency.RUB.value


def as_money(value) -> Decimal:
    if value is None:
        raise fin_error("FIN_AMOUNT_INVALID", "Amount is required")
    if isinstance(value, Decimal):
        amount = value
    else:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise fin_error("FIN_AMOUNT_INVALID", "Amount is invalid") from exc
    if amount.is_nan() or amount.is_infinite():
        raise fin_error("FIN_AMOUNT_INVALID", "Amount is invalid")
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def assert_positive(amount: Decimal) -> Decimal:
    money = as_money(amount)
    if money <= 0:
        raise fin_error("FIN_AMOUNT_INVALID", "Amount must be greater than zero")
    return money


def assert_rub(currency: str | None) -> str:
    code = (currency or "").upper()
    if code != RUB:
        raise fin_error("FIN_CURRENCY_UNSUPPORTED", "RefIQ supports only RUB")
    return RUB


def to_kopecks(amount: Decimal) -> int:
    money = as_money(amount)
    return int((money * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_kopecks(kopecks: int) -> Decimal:
    return as_money(Decimal(kopecks) / Decimal("100"))


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize SQLite-naive and aware timestamps for interval comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
