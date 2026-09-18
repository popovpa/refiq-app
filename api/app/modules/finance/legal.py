from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from app.common.enums import LegalSubjectType, LegalVerificationStatus, TaxStatus
from app.modules.finance.errors import fin_error
from app.modules.finance.models import LegalEntity

_DIGITS = re.compile(r"^\d+$")

JURIDICAL_FIELDS = (
    "subject_type",
    "tax_status",
    "inn",
    "ogrn",
    "ogrnip",
    "legal_name",
    "first_name",
    "last_name",
    "middle_name",
    "legal_address",
)


class LegalEntityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: str | None = None
    tax_status: str | None = None
    country: str | None = None
    legal_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    ogrnip: str | None = None
    legal_address: str | None = None
    submit: bool = False


def _digits(value: str | None, length: int, field: str) -> str | None:
    if not value:
        return None
    text = re.sub(r"\D", "", value)
    if not text:
        return None
    if not _DIGITS.match(text) or len(text) != length:
        labels = {"INN": "ИНН", "OGRN": "ОГРН", "OGRNIP": "ОГРНИП"}
        label = labels.get(field, field)
        raise fin_error(
            "FIN_LEGAL_ENTITY_INVALID",
            f"{label} должен содержать {length} цифр",
        )
    return text


PARTNER_INDIVIDUAL_REQUIRES_NPD = "PARTNER_INDIVIDUAL_REQUIRES_NPD"
PARTNER_TAX_STATUS_INVALID = "PARTNER_TAX_STATUS_INVALID"
PARTNER_LEGAL_TYPE_NOT_SUPPORTED = "PARTNER_LEGAL_TYPE_NOT_SUPPORTED"

PARTNER_SOLE_PROPRIETOR_TAX_STATUSES = {
    TaxStatus.NPD.value,
    TaxStatus.USN.value,
    TaxStatus.OSN.value,
    TaxStatus.PATENT.value,
    TaxStatus.OTHER.value,
}
PARTNER_LEGAL_ENTITY_TAX_STATUSES = {
    TaxStatus.USN.value,
    TaxStatus.OSN.value,
    TaxStatus.OTHER.value,
}


def validate_partner_legal_combination(
    subject_type: str | None,
    tax_status: str | None,
    *,
    submit: bool = False,
) -> None:
    """Reject Partner combinations that are not payout-eligible.

    INDIVIDUAL is allowed only as самозанятый / НПД. Ordinary individuals
    without NPD are not supported and are never auto-converted.
    """
    subject = (subject_type or "").upper()
    tax = (tax_status or TaxStatus.UNKNOWN.value).upper()
    if subject == LegalSubjectType.INDIVIDUAL.value:
        if tax != TaxStatus.NPD.value:
            raise fin_error(
                PARTNER_INDIVIDUAL_REQUIRES_NPD,
                "Для получения выплат физическое лицо должно иметь статус самозанятого / НПД.",
            )
        return
    if subject == LegalSubjectType.SOLE_PROPRIETOR.value:
        allowed = set(PARTNER_SOLE_PROPRIETOR_TAX_STATUSES)
        if not submit:
            allowed.add(TaxStatus.UNKNOWN.value)
        if tax not in allowed:
            raise fin_error(PARTNER_TAX_STATUS_INVALID, "Недопустимый налоговый статус для ИП")
        return
    if subject == LegalSubjectType.LEGAL_ENTITY.value:
        allowed = set(PARTNER_LEGAL_ENTITY_TAX_STATUSES)
        if not submit:
            allowed.add(TaxStatus.UNKNOWN.value)
        if tax not in allowed:
            raise fin_error(PARTNER_TAX_STATUS_INVALID, "Недопустимый налоговый статус для юридического лица")
        return
    raise fin_error(PARTNER_LEGAL_TYPE_NOT_SUPPORTED, "Недопустимый тип партнёра для выплат")


def validate_legal_entity_payload(data: dict, *, strict: bool = True) -> dict:
    subject = (data.get("subject_type") or LegalSubjectType.INDIVIDUAL.value).upper()
    tax = (data.get("tax_status") or TaxStatus.UNKNOWN.value).upper()
    try:
        subject_type = LegalSubjectType(subject)
        tax_status = TaxStatus(tax)
    except ValueError as exc:
        raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Некорректный тип субъекта или налоговый статус") from exc

    country = (data.get("country") or "RU").upper()
    payload = {
        "subject_type": subject_type.value,
        "tax_status": tax_status.value,
        "country": country,
        "legal_name": _text(data.get("legal_name"), 255),
        "first_name": _text(data.get("first_name"), 100),
        "last_name": _text(data.get("last_name"), 100),
        "middle_name": _text(data.get("middle_name"), 100),
        "inn": None,
        "ogrn": None,
        "ogrnip": None,
        "legal_address": _text(data.get("legal_address"), 1000),
    }

    if subject_type == LegalSubjectType.INDIVIDUAL:
        payload["inn"] = _optional_digits(data.get("inn"), 12, "INN", strict=strict)
        if strict and tax_status == TaxStatus.NPD and not (payload["first_name"] and payload["last_name"]):
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Для самозанятого укажите имя и фамилию")
        if strict and tax_status == TaxStatus.NPD and not payload["inn"]:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Для самозанятого укажите ИНН")
    elif subject_type == LegalSubjectType.SOLE_PROPRIETOR:
        payload["inn"] = _optional_digits(data.get("inn"), 12, "INN", strict=strict)
        payload["ogrnip"] = _optional_digits(data.get("ogrnip"), 15, "OGRNIP", strict=strict)
        if strict and not payload["legal_name"] and not (payload["first_name"] and payload["last_name"]):
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Для ИП укажите наименование или ФИО")
        if strict and not payload["inn"]:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Для ИП укажите ИНН")
    else:
        payload["inn"] = _optional_digits(data.get("inn"), 10, "INN", strict=strict)
        payload["ogrn"] = _optional_digits(data.get("ogrn"), 13, "OGRN", strict=strict)
        if strict and not payload["legal_name"]:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Укажите наименование юридического лица")
        if strict and not payload["inn"]:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Укажите ИНН юридического лица")
        if strict and not payload["legal_address"]:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Укажите юридический адрес")
    return payload


def _optional_digits(value: str | None, length: int, field: str, *, strict: bool) -> str | None:
    if not value:
        return None
    text = re.sub(r"\D", "", str(value))
    if not text:
        return None
    if len(text) == length and _DIGITS.match(text):
        return text
    if strict:
        return _digits(text, length, field)
    # Draft: keep partial digits so the user can finish later.
    return text[:32]


def is_complete_for_type(entity: LegalEntity) -> bool:
    try:
        validate_legal_entity_payload(
            {
                "subject_type": entity.subject_type,
                "tax_status": entity.tax_status,
                "country": entity.country,
                "legal_name": entity.legal_name,
                "first_name": entity.first_name,
                "last_name": entity.last_name,
                "middle_name": entity.middle_name,
                "inn": entity.inn,
                "ogrn": entity.ogrn,
                "ogrnip": entity.ogrnip,
                "legal_address": entity.legal_address,
            }
        )
        return True
    except Exception:
        return False


def legal_entity_full_name(entity: LegalEntity) -> str | None:
    parts = [entity.last_name, entity.first_name, entity.middle_name]
    name = " ".join(part for part in parts if part)
    return name or None


def serialize_legal_entity(entity: LegalEntity | None) -> dict | None:
    if entity is None:
        return None
    return {
        "id": entity.id,
        "subject_type": entity.subject_type,
        "tax_status": entity.tax_status,
        "country": entity.country,
        "legal_name": entity.legal_name,
        "full_name": legal_entity_full_name(entity),
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "middle_name": entity.middle_name,
        "inn": entity.inn,
        "kpp": entity.kpp,
        "ogrn": entity.ogrn,
        "ogrnip": entity.ogrnip,
        "legal_address": entity.legal_address,
        "verification_status": entity.verification_status,
        "verification_reason": entity.verification_reason,
        "verification_reason_code": entity.verification_reason_code,
        "lookup_provider": entity.lookup_provider,
        "lookup_invalid": bool(entity.lookup_invalid),
        "registry_status": entity.registry_status,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "verified_at": entity.verified_at.isoformat() if entity.verified_at else None,
    }


def reset_verification_snapshot(entity: LegalEntity) -> None:
    entity.verified_at = None
    entity.verification_source = None
    entity.verified_by_admin_id = None
    entity.verification_reason_code = None
    entity.verification_reason = None


def _text(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    return stripped[:max_len]


def is_verified(entity: LegalEntity | None) -> bool:
    return bool(entity and entity.verification_status == LegalVerificationStatus.VERIFIED.value)


def is_blocked(entity: LegalEntity | None) -> bool:
    return bool(entity and entity.verification_status == LegalVerificationStatus.BLOCKED.value)


def require_verified_legal_entity(entity: LegalEntity | None) -> LegalEntity:
    if not is_verified(entity):
        raise fin_error("FIN_LEGAL_ENTITY_NOT_VERIFIED", "Legal entity is not verified")
    return entity
