import hashlib
import hmac
import secrets

from app.core.config import settings

TOKEN_PREFIX = "rqpb_"
_TOKEN_BYTES = 32


def generate_postback_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)


def hash_postback_token(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def token_suffix(token: str) -> str:
    return token[-4:]


def mask_token(suffix: str) -> str:
    return f"{TOKEN_PREFIX}{'•' * 20}{suffix}"
