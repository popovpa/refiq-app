from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    LegalVerificationProviderType,
    LegalVerificationRejectReason,
    LegalVerificationStatus,
    VerificationAttemptStatus,
)
from app.core.exceptions import NotFoundError
from app.modules.finance.audit import record_audit
from app.modules.finance.errors import fin_error
from app.modules.finance.legal import (
    JURIDICAL_FIELDS,
    is_complete_for_type,
    reset_verification_snapshot,
    validate_legal_entity_payload,
)
from app.modules.finance.models import LegalEntity, LegalEntityVerificationAttempt

PUBLIC_REJECT_REASONS: dict[str, str] = {
    LegalVerificationRejectReason.INN_NOT_FOUND.value: "ИНН не найден",
    LegalVerificationRejectReason.ENTITY_INACTIVE.value: "Субъект не действует",
    LegalVerificationRejectReason.DATA_MISMATCH.value: "Данные не совпадают",
    LegalVerificationRejectReason.UNSUPPORTED_ENTITY_TYPE.value: "Недопустимый тип субъекта",
    LegalVerificationRejectReason.INVALID_LEGAL_DATA.value: "Некорректные юридические данные",
    LegalVerificationRejectReason.OTHER.value: "Юридические данные отклонены",
}

_RESULT_TO_ATTEMPT = {
    VerificationAttemptStatus.SUCCESS.value: LegalVerificationStatus.VERIFIED.value,
    VerificationAttemptStatus.FAILED.value: LegalVerificationStatus.REJECTED.value,
    VerificationAttemptStatus.REVIEW_REQUIRED.value: LegalVerificationStatus.REVIEW_REQUIRED.value,
    VerificationAttemptStatus.PENDING.value: LegalVerificationStatus.PENDING_VERIFICATION.value,
}


@dataclass(frozen=True)
class VerificationResult:
    status: str
    provider: str
    reason_code: str | None = None
    public_reason: str | None = None
    provider_reference: str | None = None
    normalized_data: dict | None = None
    metadata: dict = field(default_factory=dict)


class LegalEntityVerificationProvider(Protocol):
    name: str

    async def verify(self, entity: LegalEntity) -> VerificationResult: ...


class ManualVerificationProvider:
    """Packages an admin decision as a domain VerificationResult.

    Future FNS/T-Bank providers return the same VerificationResult shape;
    financial gating depends only on LegalEntity.verification_status.
    """

    name = LegalVerificationProviderType.MANUAL.value

    def __init__(
        self,
        *,
        approved: bool,
        reason_code: str | None = None,
        comment: str | None = None,
    ):
        self.approved = approved
        self.reason_code = reason_code
        self.comment = comment

    async def verify(self, entity: LegalEntity) -> VerificationResult:
        if self.approved:
            return VerificationResult(
                status=VerificationAttemptStatus.SUCCESS.value,
                provider=self.name,
                metadata={"comment": self.comment} if self.comment else {},
            )
        code = self.reason_code or LegalVerificationRejectReason.OTHER.value
        return VerificationResult(
            status=VerificationAttemptStatus.FAILED.value,
            provider=self.name,
            reason_code=code,
            public_reason=public_reason_for(code, self.comment),
            metadata={"comment": self.comment} if self.comment else {},
        )


def public_reason_for(reason_code: str | None, comment: str | None = None) -> str | None:
    if not reason_code:
        return None
    if reason_code == LegalVerificationRejectReason.OTHER.value:
        text = (comment or "").strip()
        return text or PUBLIC_REJECT_REASONS[reason_code]
    return PUBLIC_REJECT_REASONS.get(reason_code, PUBLIC_REJECT_REASONS[LegalVerificationRejectReason.OTHER.value])


class LegalEntityVerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_manual(
        self,
        legal_entity_id: int,
        actor_user_id: int | None = None,
        comment: str | None = None,
        *,
        actor_admin_id: int | None = None,
    ) -> LegalEntity:
        entity = await self._lock(legal_entity_id)
        if entity.verification_status == LegalVerificationStatus.VERIFIED.value:
            return entity
        self._require_pending(entity)
        provider = ManualVerificationProvider(approved=True, comment=comment)
        result = await provider.verify(entity)
        return await self._apply_result(
            entity,
            result,
            actor_admin_id=actor_admin_id,
            actor_user_id=actor_user_id,
            comment=comment,
        )

    async def reject_manual(
        self,
        legal_entity_id: int,
        actor_user_id: int | None = None,
        reason_code: str | None = None,
        comment: str | None = None,
        *,
        actor_admin_id: int | None = None,
    ) -> LegalEntity:
        try:
            code = LegalVerificationRejectReason(reason_code).value
        except ValueError as exc:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Invalid rejection reason") from exc
        if code == LegalVerificationRejectReason.OTHER.value and not (comment or "").strip():
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Comment is required for OTHER", 422)
        entity = await self._lock(legal_entity_id)
        if entity.verification_status == LegalVerificationStatus.REJECTED.value:
            return entity
        self._require_pending(entity)
        provider = ManualVerificationProvider(approved=False, reason_code=code, comment=comment)
        result = await provider.verify(entity)
        return await self._apply_result(
            entity,
            result,
            actor_admin_id=actor_admin_id,
            actor_user_id=actor_user_id,
            comment=comment,
        )

    async def apply_user_update(
        self,
        legal_entity_id: int,
        data: dict,
        *,
        submit: bool,
        actor_user_id: int,
    ) -> LegalEntity:
        entity = await self._lock(legal_entity_id)
        payload = validate_legal_entity_payload({**_entity_fields(entity), **data}, strict=submit)
        old_status = entity.verification_status
        changed_fields = [
            key
            for key in JURIDICAL_FIELDS
            if (getattr(entity, key, None) or None) != (payload.get(key) or None)
        ]
        changed = bool(changed_fields)
        if old_status == LegalVerificationStatus.BLOCKED.value and (submit or changed):
            raise fin_error(
                "LEGAL_ENTITY_STATUS_CHANGED",
                "Blocked legal entity cannot be changed",
                409,
            )
        for key, value in payload.items():
            setattr(entity, key, value)

        new_status = old_status
        reverification = False
        if submit:
            if old_status == LegalVerificationStatus.VERIFIED.value:
                if changed:
                    new_status = LegalVerificationStatus.PENDING_VERIFICATION.value
                    reset_verification_snapshot(entity)
                    reverification = True
            else:
                new_status = LegalVerificationStatus.PENDING_VERIFICATION.value
                if old_status in {
                    LegalVerificationStatus.REJECTED.value,
                    LegalVerificationStatus.REVIEW_REQUIRED.value,
                }:
                    reset_verification_snapshot(entity)
        elif changed and old_status == LegalVerificationStatus.VERIFIED.value:
            new_status = (
                LegalVerificationStatus.PENDING_VERIFICATION.value
                if is_complete_for_type(entity)
                else LegalVerificationStatus.DRAFT.value
            )
            reset_verification_snapshot(entity)
            reverification = True

        entity.verification_status = new_status
        if submit or reverification:
            entity.verification_reason = None
            entity.verification_reason_code = None

        await record_audit(
            self.db,
            action="legal_entity.updated",
            entity_type="legal_entity",
            entity_id=entity.id,
            actor_user_id=actor_user_id,
            old_status=old_status,
            new_status=entity.verification_status,
        )
        if reverification:
            await record_audit(
                self.db,
                action="LEGAL_ENTITY_REVERIFICATION_REQUIRED",
                entity_type="legal_entity",
                entity_id=entity.id,
                actor_user_id=actor_user_id,
                old_status=old_status,
                new_status=entity.verification_status,
                metadata={"changed_fields": changed_fields},
            )
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def _lock(self, legal_entity_id: int) -> LegalEntity:
        entity = await self.db.scalar(
            select(LegalEntity).where(LegalEntity.id == legal_entity_id).with_for_update()
        )
        if not entity:
            raise NotFoundError("LegalEntity")
        return entity

    def _require_pending(self, entity: LegalEntity) -> None:
        if entity.verification_status != LegalVerificationStatus.PENDING_VERIFICATION.value:
            raise fin_error(
                "LEGAL_ENTITY_STATUS_CHANGED",
                "Legal entity status has changed",
                409,
            )

    async def _apply_result(
        self,
        entity: LegalEntity,
        result: VerificationResult,
        *,
        actor_admin_id: int | None,
        actor_user_id: int | None,
        comment: str | None,
    ) -> LegalEntity:
        now = datetime.now(timezone.utc)
        new_status = _RESULT_TO_ATTEMPT.get(result.status)
        if not new_status:
            raise fin_error("FIN_LEGAL_ENTITY_INVALID", "Unsupported verification result")

        attempt = LegalEntityVerificationAttempt(
            legal_entity_id=entity.id,
            provider=result.provider,
            status=result.status,
            actor_admin_id=actor_admin_id,
            actor_user_id=actor_user_id,
            reason_code=result.reason_code,
            public_reason=result.public_reason,
            comment=(comment or "").strip() or None,
            requested_at=now,
            completed_at=now,
            provider_request_id=result.provider_reference,
            metadata_=result.metadata or None,
        )
        self.db.add(attempt)

        old_status = entity.verification_status
        entity.verification_status = new_status
        entity.verification_source = result.provider
        if new_status == LegalVerificationStatus.VERIFIED.value:
            entity.verified_at = now
            entity.verified_by_admin_id = actor_admin_id
            entity.verification_reason = None
            entity.verification_reason_code = None
            audit_action = "LEGAL_ENTITY_VERIFIED"
        elif new_status == LegalVerificationStatus.REJECTED.value:
            entity.verified_at = None
            entity.verified_by_admin_id = actor_admin_id
            entity.verification_reason_code = result.reason_code
            entity.verification_reason = result.public_reason
            audit_action = "LEGAL_ENTITY_REJECTED"
        else:
            entity.verified_at = None
            entity.verification_reason_code = result.reason_code
            entity.verification_reason = result.public_reason
            audit_action = "LEGAL_ENTITY_REVERIFICATION_REQUIRED"

        await record_audit(
            self.db,
            action=audit_action,
            entity_type="legal_entity",
            entity_id=entity.id,
            actor_user_id=actor_user_id,
            system_actor=f"admin:{actor_admin_id}" if actor_admin_id is not None else result.provider,
            old_status=old_status,
            new_status=entity.verification_status,
            reason=result.reason_code,
            metadata={
                "legal_entity_id": entity.id,
                "reason_code": result.reason_code,
                "comment": (comment or "").strip() or None,
                "admin_user_id": actor_admin_id,
                "provider": result.provider,
                "attempt_status": result.status,
            },
        )
        await self.db.flush()
        await self.db.refresh(entity)
        return entity


def _entity_fields(entity: LegalEntity) -> dict:
    return {
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
