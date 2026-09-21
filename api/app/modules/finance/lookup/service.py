from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, LegalVerificationStatus, TaxStatus
from app.core.ids import parse_id
from app.core.redis import redis_client
from app.modules.businesses.models import Business
from app.modules.finance.audit import record_audit
from app.modules.finance.billing import ensure_billing_profile
from app.modules.finance.bootstrap import ensure_payout_profile
from app.modules.finance.legal import legal_entity_full_name, serialize_legal_entity
from app.modules.finance.lookup.access import (
    context_allows_subject,
    normalize_inn,
    usage_labels_for_user,
    user_accessible_legal_entities,
    user_accessible_legal_entity_ids,
)
from app.modules.finance.lookup.candidate_token import (
    decode_candidate,
    encode_external_candidate,
    encode_local_candidate,
    reference_from_payload,
)
from app.modules.finance.lookup.errors import lookup_error
from app.modules.finance.lookup.factory import current_lookup_provider_name, get_lookup_provider
from app.modules.finance.lookup.protocol import LegalEntityCandidate, ResolvedLegalEntity
from app.modules.finance.metrics import inc
from app.modules.finance.models import LegalEntity
from app.modules.partners.models import PartnerProfile
SEARCH_LIMIT = 10
SEARCH_RATE_LIMIT = 30
SELECT_RATE_LIMIT = 20


def _skip_external_lookup(*, context: str, subject_type: str | None) -> bool:
    return context == "partner" and subject_type == LegalSubjectType.INDIVIDUAL.value


def _local_matches(entity: LegalEntity, query: str) -> bool:
    needle = query.strip().casefold()
    digits = "".join(ch for ch in query if ch.isdigit())
    if digits and entity.inn and entity.inn.startswith(digits):
        return True
    haystacks = [
        entity.legal_name,
        legal_entity_full_name(entity),
        entity.first_name,
        entity.last_name,
        entity.inn,
        entity.ogrn,
        entity.ogrnip,
    ]
    return any(value and needle in str(value).casefold() for value in haystacks)


def serialize_public_candidate(
    candidate: LegalEntityCandidate,
    *,
    candidate_id: str,
    existing_legal_entity_id: int | None = None,
    reuse_available: bool = False,
    verification_status: str | None = None,
    used_in: list[str] | None = None,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "display_name": candidate.display_name,
        "subject_type": candidate.subject_type,
        "inn": candidate.inn,
        "kpp": candidate.kpp,
        "ogrn": candidate.ogrn,
        "ogrnip": candidate.ogrnip,
        "opf": candidate.opf,
        "region": candidate.region,
        "address_summary": candidate.address_summary,
        "status": candidate.status,
        "existing_legal_entity_id": existing_legal_entity_id,
        "reuse_available": reuse_available,
        "verification_status": verification_status,
        "used_in": used_in or [],
    }


async def _rate_limit(key: str, limit: int) -> None:
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 60)
    if count > limit:
        raise lookup_error("LEGAL_ENTITY_LOOKUP_RATE_LIMITED", status_code=429)


class LegalEntityLookupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        *,
        user_id: int,
        query: str,
        context: str,
        subject_type: str | None,
    ) -> dict:
        query = (query or "").strip()
        if len(query) < 3 and not (query.isdigit() and len(query) in {10, 12}):
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
        if context not in {"business", "partner"}:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
        await _rate_limit(f"legal_lookup:search:{user_id}", SEARCH_RATE_LIMIT)
        provider_name = current_lookup_provider_name()
        inc(f"legal_entity_lookup_requests_total.{provider_name}")
        started = time.perf_counter()
        try:
            local = await self._local_candidates(user_id, query, context, subject_type)
            external: list[dict] = []
            if not _skip_external_lookup(context=context, subject_type=subject_type):
                external = await self._external_candidates(query, context, local, subject_type)
            merged = self._merge(local, external)[:SEARCH_LIMIT]
            inc(f"legal_entity_lookup_success_total.{provider_name}")
            return {"items": merged, "lookup_enabled": not _skip_external_lookup(context=context, subject_type=subject_type)}
        except Exception:
            inc(f"legal_entity_lookup_error_total.{provider_name}")
            raise
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            inc(f"legal_entity_lookup_latency_ms.{provider_name}", elapsed_ms)

    async def select(
        self,
        *,
        user_id: int,
        candidate_id: str,
        target_context: str,
        business_id: int | None,
    ) -> dict:
        if target_context not in {"business", "partner"}:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")
        await self._require_context(user_id, target_context)
        await _rate_limit(f"legal_lookup:select:{user_id}", SELECT_RATE_LIMIT)
        provider_name = current_lookup_provider_name()
        entity, reused = await self.materialize(user_id=user_id, candidate_id=candidate_id, context=target_context)
        await self._bind(user_id, entity, target_context, business_id)
        if reused:
            inc(f"legal_entity_lookup_reuse_total.{provider_name}")
        else:
            inc(f"legal_entity_lookup_created_total.{provider_name}")
        await record_audit(
            self.db,
            action="legal_entity.reused" if reused else "legal_entity.created_from_lookup",
            entity_type="legal_entity",
            entity_id=entity.id,
            actor_user_id=user_id,
            new_status=entity.verification_status,
            metadata={"context": target_context, "reused": reused},
        )
        return {
            "legal_entity": serialize_legal_entity(entity),
            "reused": reused,
        }

    async def materialize(
        self,
        *,
        user_id: int,
        candidate_id: str,
        context: str,
    ) -> tuple[LegalEntity, bool]:
        """Resolve or reuse a LegalEntity without binding it to a profile."""
        payload = decode_candidate(candidate_id)
        if payload.get("src") == "local":
            return await self._select_local(user_id, payload, context)
        if payload.get("src") == "external":
            return await self._select_external(user_id, payload, context)
        raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST")

    async def _require_context(self, user_id: int, context: str) -> None:
        if context == "partner":
            partner = await self.db.scalar(select(PartnerProfile).where(PartnerProfile.user_id == user_id))
            if not partner:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "Partner profile required", 403)
            return
        from app.modules.businesses.models import BusinessMembership
        from app.common.enums import MembershipStatus

        membership = await self.db.scalar(
            select(BusinessMembership.id).where(
                BusinessMembership.user_id == user_id,
                BusinessMembership.status == MembershipStatus.ACTIVE.value,
            )
        )
        if not membership:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "Business membership required", 403)

    async def _local_candidates(
        self,
        user_id: int,
        query: str,
        context: str,
        subject_type: str | None,
    ) -> list[dict]:
        items: list[dict] = []
        for entity in await user_accessible_legal_entities(self.db, user_id):
            if subject_type and entity.subject_type != subject_type:
                continue
            if not context_allows_subject(context, entity.subject_type):
                continue
            if not _local_matches(entity, query):
                continue
            used_in = await usage_labels_for_user(self.db, user_id, entity.id)
            candidate = LegalEntityCandidate(
                provider="refiq",
                display_name=entity.legal_name or legal_entity_full_name(entity) or f"ИНН {entity.inn or entity.id}",
                subject_type=entity.subject_type,
                inn=entity.inn or "",
                kpp=entity.kpp,
                ogrn=entity.ogrn,
                ogrnip=entity.ogrnip,
                region=None,
                address_summary=entity.legal_address,
                status="ACTIVE",
            )
            items.append(
                serialize_public_candidate(
                    candidate,
                    candidate_id=encode_local_candidate(
                        legal_entity_id=entity.id,
                        inn=entity.inn,
                        subject_type=entity.subject_type,
                    ),
                    existing_legal_entity_id=entity.id,
                    reuse_available=True,
                    verification_status=entity.verification_status,
                    used_in=used_in,
                )
            )
        return items

    async def _external_candidates(
        self, query: str, context: str, local: list[dict], subject_type: str | None
    ) -> list[dict]:
        provider = get_lookup_provider()
        found = await provider.search(query, context=context, limit=SEARCH_LIMIT)
        local_inns = {(item.get("inn"), item.get("subject_type")) for item in local}
        items: list[dict] = []
        for candidate in found:
            if subject_type and candidate.subject_type != subject_type:
                continue
            if not context_allows_subject(context, candidate.subject_type):
                continue
            key = (candidate.inn, candidate.subject_type)
            if key in local_inns:
                continue
            if not candidate.reference:
                continue
            items.append(
                serialize_public_candidate(
                    candidate,
                    candidate_id=encode_external_candidate(candidate.reference),
                )
            )
        return items

    def _merge(self, local: list[dict], external: list[dict]) -> list[dict]:
        return [*local, *external]

    async def _select_local(self, user_id: int, payload: dict, context: str) -> tuple[LegalEntity, bool]:
        try:
            legal_entity_id = parse_id(payload.get("legal_entity_id"))
        except (TypeError, ValueError) as exc:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST") from exc
        allowed = await user_accessible_legal_entity_ids(self.db, user_id)
        if legal_entity_id not in allowed:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "Legal entity is not available", 403)
        entity = await self.db.get(LegalEntity, legal_entity_id)
        if not entity:
            raise lookup_error("LEGAL_ENTITY_NOT_FOUND", status_code=404)
        if not context_allows_subject(context, entity.subject_type):
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", status_code=403)
        return entity, True

    async def _select_external(self, user_id: int, payload: dict, context: str) -> tuple[LegalEntity, bool]:
        reference = reference_from_payload(payload)
        if not context_allows_subject(context, reference.subject_type):
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", status_code=403)
        resolved = await get_lookup_provider().resolve(reference)
        if resolved.registry_status != "ACTIVE":
            raise lookup_error("LEGAL_ENTITY_NOT_ACTIVE", status_code=409)
        if not context_allows_subject(context, resolved.subject_type):
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", status_code=403)
        existing = await self._find_accessible_by_identity(user_id, resolved)
        if existing:
            return existing, True
        return await self._create_from_resolved(user_id, resolved), False

    async def _find_accessible_by_identity(self, user_id: int, resolved: ResolvedLegalEntity) -> LegalEntity | None:
        inn = normalize_inn(resolved.inn)
        if not inn:
            return None
        for entity in await user_accessible_legal_entities(self.db, user_id):
            if (
                (entity.country or "RU").upper() == "RU"
                and normalize_inn(entity.inn) == inn
                and entity.subject_type == resolved.subject_type
            ):
                return entity
        return None

    async def _create_from_resolved(self, user_id: int, resolved: ResolvedLegalEntity) -> LegalEntity:
        now = datetime.now(timezone.utc)
        entity = LegalEntity(
            subject_type=resolved.subject_type,
            tax_status=TaxStatus.UNKNOWN.value,
            country="RU",
            legal_name=resolved.legal_name,
            first_name=resolved.first_name,
            last_name=resolved.last_name,
            middle_name=resolved.middle_name,
            inn=resolved.inn,
            kpp=resolved.kpp,
            ogrn=resolved.ogrn,
            ogrnip=resolved.ogrnip,
            legal_address=resolved.legal_address,
            verification_status=LegalVerificationStatus.PENDING_VERIFICATION.value,
            lookup_provider=resolved.provider,
            lookup_provider_reference=(resolved.provider_reference or resolved.inn)[:128],
            lookup_at=now,
            registry_status=resolved.registry_status,
            lookup_invalid=resolved.invalid,
            lookup_metadata={
                "opf_code": resolved.opf_code,
                "opf_short": resolved.opf_short,
                "opf_full": resolved.opf_full,
                "region": resolved.region,
                "registry_actuality_date": resolved.registry_actuality_date.isoformat()
                if resolved.registry_actuality_date
                else None,
                "invalid": resolved.invalid,
            },
        )
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def _bind(self, user_id: int, entity: LegalEntity, context: str, business_id: int | None) -> None:
        if context == "partner":
            partner = await self.db.scalar(select(PartnerProfile).where(PartnerProfile.user_id == user_id))
            if not partner:
                raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", status_code=403)
            partner.legal_entity_id = entity.id
            await ensure_payout_profile(self.db, partner)
            return
        if not business_id:
            from app.common.enums import MembershipStatus
            from app.modules.businesses.models import BusinessMembership

            business_id = await self.db.scalar(
                select(BusinessMembership.business_id).where(
                    BusinessMembership.user_id == user_id,
                    BusinessMembership.status == MembershipStatus.ACTIVE.value,
                )
            )
        if not business_id:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "No active business", 403)
        business = await self.db.get(Business, business_id)
        if not business:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", "Business not found", 404)
        from app.modules.finance.permissions import load_business_membership

        membership = await load_business_membership(self.db, user_id, business.id)
        if not membership:
            raise lookup_error("LEGAL_ENTITY_LOOKUP_INVALID_REQUEST", status_code=403)
        business.legal_entity_id = entity.id
        business.legal_name = entity.legal_name
        business.country = entity.country
        await ensure_billing_profile(self.db, business)
