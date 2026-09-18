from __future__ import annotations

from app.modules.finance.errors import FinancialError, fin_error

LOOKUP_MESSAGES = {
    "LEGAL_ENTITY_LOOKUP_INVALID_REQUEST": "Некорректный запрос поиска организации",
    "LEGAL_ENTITY_LOOKUP_UNAVAILABLE": "Не удалось выполнить поиск. Попробуйте ещё раз или заполните данные вручную.",
    "LEGAL_ENTITY_LOOKUP_RATE_LIMITED": "Слишком много запросов. Подождите немного и повторите поиск.",
    "LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR": "Поиск организаций временно недоступен.",
    "LEGAL_ENTITY_NOT_FOUND": "Организация не найдена",
    "LEGAL_ENTITY_NOT_ACTIVE": "Организация не действует и не может быть использована",
}


def lookup_error(code: str, message: str | None = None, status_code: int = 400) -> FinancialError:
    return fin_error(code, message or LOOKUP_MESSAGES.get(code, "Lookup error"), status_code)
