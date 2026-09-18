from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CandidateReference:
    provider: str
    inn: str
    subject_type: str
    kpp: str | None = None
    branch_type: str | None = None
    ogrn: str | None = None


@dataclass
class LegalEntityCandidate:
    provider: str
    display_name: str
    subject_type: str
    inn: str
    reference: CandidateReference | None = None
    kpp: str | None = None
    ogrn: str | None = None
    ogrnip: str | None = None
    opf: str | None = None
    region: str | None = None
    address_summary: str | None = None
    status: str = "ACTIVE"
    invalid: bool = False


@dataclass
class ResolvedLegalEntity:
    provider: str
    provider_reference: str | None
    subject_type: str
    legal_name: str | None
    first_name: str | None
    last_name: str | None
    middle_name: str | None
    inn: str
    kpp: str | None
    ogrn: str | None
    ogrnip: str | None
    opf_code: str | None
    opf_short: str | None
    opf_full: str | None
    legal_address: str | None
    region: str | None
    registry_status: str
    registration_date: datetime | None
    registry_actuality_date: datetime | None
    invalid: bool = False
    metadata: dict = field(default_factory=dict)


class LegalEntityLookupProvider(Protocol):
    name: str

    async def search(self, query: str, *, context: str, limit: int) -> list[LegalEntityCandidate]: ...

    async def resolve(self, reference: CandidateReference) -> ResolvedLegalEntity: ...
