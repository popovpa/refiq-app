from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings
from app.modules.finance.lookup.errors import lookup_error
from app.modules.finance.lookup.protocol import CandidateReference

CANDIDATE_TTL_SECONDS = 900


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_candidate(payload: dict) -> str:
    body = {**payload, "exp": int(time.time()) + CANDIDATE_TTL_SECONDS}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64encode(raw)}.{_b64encode(signature)}"


def decode_candidate(token: str) -> dict:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _b64decode(raw_b64)
        signature = _b64decode(sig_b64)
    except (ValueError, IndexError) as exc:
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST") from exc
    expected = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST") from exc
    if int(payload.get("exp") or 0) < int(time.time()):
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "Истекло время выбора организации")
    return payload


def encode_local_candidate(*, legal_entity_id: int, inn: str | None, subject_type: str) -> str:
    return sign_candidate(
        {
            "src": "local",
            "legal_entity_id": legal_entity_id,
            "inn": inn,
            "subject_type": subject_type,
        }
    )


def encode_external_candidate(reference: CandidateReference) -> str:
    return sign_candidate(
        {
            "src": "external",
            "provider": reference.provider,
            "inn": reference.inn,
            "kpp": reference.kpp,
            "subject_type": reference.subject_type,
            "branch_type": reference.branch_type,
            "ogrn": reference.ogrn,
        }
    )


def reference_from_payload(payload: dict) -> CandidateReference:
    inn = "".join(ch for ch in str(payload.get("inn") or "") if ch.isdigit())
    if not inn:
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
    return CandidateReference(
        provider=str(payload.get("provider") or ""),
        inn=inn,
        subject_type=str(payload.get("subject_type") or ""),
        kpp=payload.get("kpp") or None,
        branch_type=payload.get("branch_type") or None,
        ogrn=payload.get("ogrn") or None,
    )
