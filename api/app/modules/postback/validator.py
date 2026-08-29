import re

from app.core.exceptions import AppError
from app.modules.postback.dto import PostbackRequest

RQCID_PATTERN = re.compile(r"^[a-z0-9]{12}$")

UNAUTHORIZED = ("UNAUTHORIZED", "Invalid or missing token", 401)
INVALID_POSTBACK = ("INVALID_POSTBACK", "Invalid parameters or token", 400)


def unauthorized() -> AppError:
    return AppError(code=UNAUTHORIZED[0], message=UNAUTHORIZED[1], status_code=UNAUTHORIZED[2])


def invalid_postback() -> AppError:
    return AppError(code=INVALID_POSTBACK[0], message=INVALID_POSTBACK[1], status_code=INVALID_POSTBACK[2])


class PostbackValidator:
    def parse_bearer(self, authorization: str | None) -> str:
        if not authorization:
            raise unauthorized()
        scheme, _, value = authorization.partition(" ")
        token = value.strip()
        if scheme != "Bearer" or not token:
            raise unauthorized()
        return token

    def validate_request(self, payload: PostbackRequest) -> None:
        if not RQCID_PATTERN.fullmatch(payload.rqcid or ""):
            raise invalid_postback()
        if payload.amount is not None and payload.amount < 0:
            raise invalid_postback()
        if payload.currency is not None:
            currency = payload.currency.strip().upper()
            if len(currency) != 3:
                raise invalid_postback()
            payload.currency = currency
