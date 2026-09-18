from __future__ import annotations

from app.modules.finance.lookup.errors import lookup_error
from app.modules.finance.lookup.protocol import CandidateReference, LegalEntityCandidate, ResolvedLegalEntity


class FakeLegalEntityLookupProvider:
    name = "fake"

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.search_results: list[LegalEntityCandidate] = []
        self.search_error: Exception | None = None
        self.search_calls: list[dict] = []
        self.resolve_result: ResolvedLegalEntity | None = None
        self.resolve_error: Exception | None = None
        self.resolve_calls: list[CandidateReference] = []

    async def search(self, query: str, *, context: str, limit: int) -> list[LegalEntityCandidate]:
        self.search_calls.append({"query": query, "context": context, "limit": limit})
        if self.search_error:
            raise self.search_error
        return list(self.search_results[:limit])

    async def resolve(self, reference: CandidateReference) -> ResolvedLegalEntity:
        self.resolve_calls.append(reference)
        if self.resolve_error:
            raise self.resolve_error
        if self.resolve_result:
            return self.resolve_result
        raise lookup_error("LEGAL_ENTITY_NOT_FOUND", status_code=404)


fake_lookup_provider = FakeLegalEntityLookupProvider()
