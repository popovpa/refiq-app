from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LegalSubjectType, LegalVerificationStatus, TaxStatus
from app.modules.finance.legal import validate_legal_entity_payload, validate_partner_legal_combination
from app.modules.finance.lookup.service import LegalEntityLookupService
from app.modules.finance.models import LegalEntity

_OVERLAY_FIELDS = (
    "subject_type",
    "tax_status",
    "country",
    "legal_name",
    "first_name",
    "last_name",
    "middle_name",
    "inn",
    "ogrn",
    "ogrnip",
    "legal_address",
)


async def legal_entity_from_onboarding(
    db: AsyncSession,
    *,
    user_id: int,
    context: str,
    candidate_id: str | None,
    payload: dict,
    partner: bool,
) -> LegalEntity:
    if partner:
        subject = payload.get("subject_type") or LegalSubjectType.INDIVIDUAL.value
        tax = payload.get("tax_status")
        if subject == LegalSubjectType.INDIVIDUAL.value and not tax:
            tax = TaxStatus.NPD.value
            payload = {**payload, "tax_status": tax}
        require_complete = subject == LegalSubjectType.INDIVIDUAL.value
        validate_partner_legal_combination(subject, tax, submit=require_complete)
    fields = validate_legal_entity_payload(payload, strict=True)
    entity: LegalEntity | None = None
    if candidate_id:
        entity, _reused = await LegalEntityLookupService(db).materialize(
            user_id=user_id,
            candidate_id=candidate_id,
            context=context,
        )
    if entity is None:
        entity = LegalEntity(verification_status=LegalVerificationStatus.DRAFT.value)
        db.add(entity)
    for key in _OVERLAY_FIELDS:
        value = fields.get(key)
        if value is not None and value != "":
            setattr(entity, key, value)
    await db.flush()
    return entity
