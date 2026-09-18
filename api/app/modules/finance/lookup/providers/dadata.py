from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from app.common.enums import LegalSubjectType
from app.core.config import settings
from app.modules.finance.lookup.errors import lookup_error
from app.modules.finance.lookup.protocol import CandidateReference, LegalEntityCandidate, ResolvedLegalEntity

logger = structlog.get_logger()

_RETRYABLE_STATUS = {500, 502, 503, 504}


def _digits(value: object) -> str | None:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    return text or None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ms_to_dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _address(data: dict) -> str | None:
    address = data.get("address") or {}
    nested = address.get("data") if isinstance(address, dict) else None
    if isinstance(nested, dict):
        source = _text(nested.get("source"))
        if source:
            return source
    if isinstance(address, dict):
        return _text(address.get("unrestricted_value")) or _text(address.get("value"))
    return None


def _region(data: dict) -> str | None:
    address = data.get("address") or {}
    nested = address.get("data") if isinstance(address, dict) else None
    if isinstance(nested, dict):
        return _text(nested.get("region_with_type")) or _text(nested.get("city")) or _text(nested.get("region"))
    return None


def _subject_type(dadata_type: str | None) -> str | None:
    if dadata_type == "LEGAL":
        return LegalSubjectType.LEGAL_ENTITY.value
    if dadata_type == "INDIVIDUAL":
        return LegalSubjectType.SOLE_PROPRIETOR.value
    return None


def _dadata_type(subject_type: str | None) -> str | None:
    if subject_type == LegalSubjectType.LEGAL_ENTITY.value:
        return "LEGAL"
    if subject_type == LegalSubjectType.SOLE_PROPRIETOR.value:
        return "INDIVIDUAL"
    return None


def map_suggestion(item: dict) -> LegalEntityCandidate | None:
    data = item.get("data") if isinstance(item, dict) else None
    if not isinstance(data, dict):
        return None
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    if (state.get("status") or "").upper() != "ACTIVE":
        return None
    subject_type = _subject_type(data.get("type"))
    if not subject_type:
        return None
    if subject_type == LegalSubjectType.LEGAL_ENTITY.value and (data.get("branch_type") or "MAIN") != "MAIN":
        return None
    inn = _digits(data.get("inn"))
    if not inn:
        return None
    ogrn = _digits(data.get("ogrn"))
    name = data.get("name") if isinstance(data.get("name"), dict) else {}
    display = (
        _text(name.get("short_with_opf"))
        or _text(name.get("full_with_opf"))
        or _text(item.get("value"))
        or inn
    )
    opf = data.get("opf") if isinstance(data.get("opf"), dict) else {}
    return LegalEntityCandidate(
        provider="dadata",
        reference=CandidateReference(
            provider="dadata",
            inn=inn,
            subject_type=subject_type,
            kpp=_digits(data.get("kpp")),
            branch_type="MAIN" if subject_type == LegalSubjectType.LEGAL_ENTITY.value else None,
            ogrn=ogrn,
        ),
        display_name=display,
        subject_type=subject_type,
        inn=inn,
        kpp=_digits(data.get("kpp")),
        ogrn=ogrn if subject_type == LegalSubjectType.LEGAL_ENTITY.value else None,
        ogrnip=ogrn if subject_type == LegalSubjectType.SOLE_PROPRIETOR.value else None,
        opf=_text(opf.get("short")) or _text(opf.get("full")),
        region=_region(data),
        address_summary=_address(data),
        status="ACTIVE",
        invalid=bool(data.get("invalid")),
    )


def map_resolved(item: dict) -> ResolvedLegalEntity:
    data = item.get("data") if isinstance(item, dict) else {}
    if not isinstance(data, dict):
        data = {}
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    status = (state.get("status") or "").upper() or "UNKNOWN"
    subject_type = _subject_type(data.get("type")) or LegalSubjectType.LEGAL_ENTITY.value
    inn = _digits(data.get("inn")) or ""
    ogrn = _digits(data.get("ogrn"))
    name = data.get("name") if isinstance(data.get("name"), dict) else {}
    fio = data.get("fio") if isinstance(data.get("fio"), dict) else {}
    opf = data.get("opf") if isinstance(data.get("opf"), dict) else {}
    legal_name = _text(name.get("full_with_opf")) or _text(item.get("value"))
    first_name = last_name = middle_name = None
    if subject_type == LegalSubjectType.SOLE_PROPRIETOR.value:
        last_name = _text(fio.get("surname"))
        first_name = _text(fio.get("name"))
        middle_name = _text(fio.get("patronymic"))
        if not legal_name:
            legal_name = " ".join(part for part in (last_name, first_name, middle_name) if part) or None
    return ResolvedLegalEntity(
        provider="dadata",
        provider_reference=inn or ogrn,
        subject_type=subject_type,
        legal_name=legal_name,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        inn=inn,
        kpp=_digits(data.get("kpp")) if subject_type == LegalSubjectType.LEGAL_ENTITY.value else None,
        ogrn=ogrn if subject_type == LegalSubjectType.LEGAL_ENTITY.value else None,
        ogrnip=ogrn if subject_type == LegalSubjectType.SOLE_PROPRIETOR.value else None,
        opf_code=_text(opf.get("code")),
        opf_short=_text(opf.get("short")),
        opf_full=_text(opf.get("full")),
        legal_address=_address(data),
        region=_region(data),
        registry_status=status,
        registration_date=_ms_to_dt(state.get("registration_date")),
        registry_actuality_date=_ms_to_dt(state.get("actuality_date")),
        invalid=bool(data.get("invalid")),
        metadata={
            "hid": _text(data.get("hid")),
            "branch_type": _text(data.get("branch_type")),
        },
    )


class DaDataLegalEntityLookupProvider:
    name = "dadata"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        host: str | None = None,
        prefix: str | None = None,
        search_timeout: float | None = None,
        resolve_timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.DADATA_API_KEY
        self.host = (host or settings.DADATA_HOST).rstrip("/")
        prefix = prefix if prefix is not None else settings.DADATA_API_PREFIX
        self.prefix = prefix if prefix.startswith("/") else f"/{prefix}"
        self.search_timeout = search_timeout or settings.LEGAL_ENTITY_LOOKUP_SEARCH_TIMEOUT_SECONDS
        self.resolve_timeout = resolve_timeout or settings.LEGAL_ENTITY_LOOKUP_RESOLVE_TIMEOUT_SECONDS
        self._client = client

    async def search(self, query: str, *, context: str, limit: int) -> list[LegalEntityCandidate]:
        payload = await self._post(
            "/suggest/party",
            {"query": query, "count": min(limit, 10), "status": ["ACTIVE"]},
            timeout=self.search_timeout,
        )
        candidates: list[LegalEntityCandidate] = []
        for item in payload.get("suggestions") or []:
            mapped = map_suggestion(item)
            if mapped:
                candidates.append(mapped)
            if len(candidates) >= limit:
                break
        return candidates

    async def resolve(self, reference: CandidateReference) -> ResolvedLegalEntity:
        body: dict = {"query": reference.inn or reference.ogrn}
        dadata_type = _dadata_type(reference.subject_type)
        if dadata_type:
            body["type"] = dadata_type
        if reference.subject_type == LegalSubjectType.LEGAL_ENTITY.value:
            body["branch_type"] = reference.branch_type or "MAIN"
            if reference.kpp:
                body["kpp"] = reference.kpp
        payload = await self._post("/findById/party", body, timeout=self.resolve_timeout)
        suggestions = payload.get("suggestions") or []
        if not suggestions:
            raise lookup_error("LEGAL_ENTITY_NOT_FOUND", status_code=404)
        resolved = map_resolved(suggestions[0])
        if resolved.registry_status != "ACTIVE":
            raise lookup_error("LEGAL_ENTITY_NOT_ACTIVE", status_code=409)
        if resolved.subject_type == LegalSubjectType.LEGAL_ENTITY.value:
            branch = (resolved.metadata or {}).get("branch_type")
            if branch and branch != "MAIN":
                raise lookup_error("LEGAL_ENTITY_NOT_ACTIVE", status_code=409)
        if not resolved.inn:
            raise lookup_error("LEGAL_ENTITY_NOT_FOUND", status_code=404)
        return resolved

    async def _post(self, path: str, body: dict, *, timeout: float) -> dict:
        if not self.api_key:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR", status_code=503)
        url = f"https://{self.host}{self.prefix}{path}"
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                if self._client:
                    response = await self._client.post(url, json=body, headers=headers)
                else:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url, json=body, headers=headers)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt == 0:
                    continue
                logger.warning("legal_entity_lookup_timeout", provider="dadata", path=path)
                raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 0:
                    continue
                logger.warning("legal_entity_lookup_http_error", provider="dadata", path=path)
                raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503) from exc
            if response.status_code in {401, 403}:
                logger.error("legal_entity_lookup_auth_failed", provider="dadata")
                raise lookup_error("LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR", status_code=503)
            if response.status_code == 429:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_RATE_LIMITED", status_code=429)
            if response.status_code == 400:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
            if response.status_code in _RETRYABLE_STATUS:
                if attempt == 0:
                    continue
                raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503)
            if response.status_code >= 400:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503)
            try:
                return response.json()
            except ValueError as exc:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503) from exc
        raise lookup_error("LEGAL_ENTITY_LOOKUP_UNAVAILABLE", status_code=503) from last_error
