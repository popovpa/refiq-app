from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.ids import parse_id
from app.modules.postback.dto import PostbackCredentialStatus, PostbackTokenCreated
from app.modules.postback.models import PostbackCredential
from app.modules.postback.repository import PostbackRepository
from app.modules.postback.token import generate_postback_token, hash_postback_token, token_suffix
from app.modules.system.audit import write_audit_log


class PostbackCredentialService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = PostbackRepository(db)

    async def get_status(self, business_id: int) -> PostbackCredentialStatus:
        credential = await self.repository.get_active_by_business(business_id)
        if not credential:
            return PostbackCredentialStatus(configured=False, integration_status="not_configured")
        return PostbackCredentialStatus(
            configured=True,
            token_suffix=credential.token_suffix,
            created_at=credential.created_at,
            last_success_at=credential.last_success_at,
            token_status="active",
            integration_status="connected" if credential.last_success_at else "awaiting_first_request",
        )

    async def create(self, business_id: int, user_id: str | int) -> PostbackTokenCreated:
        existing = await self.repository.get_active_by_business(business_id)
        if existing:
            raise AppError(code="CONFLICT", message="Bearer Token already exists", status_code=409)
        return await self._issue(business_id, user_id, previous=None)

    async def rotate(self, business_id: int, user_id: str | int) -> PostbackTokenCreated:
        existing = await self.repository.get_active_by_business(business_id)
        return await self._issue(business_id, user_id, previous=existing)

    async def _issue(
        self,
        business_id: int,
        user_id: str | int,
        previous: PostbackCredential | None,
    ) -> PostbackTokenCreated:
        now = datetime.now(timezone.utc)
        plaintext = generate_postback_token()
        suffix = token_suffix(plaintext)
        last_success_at = previous.last_success_at if previous else None
        if previous:
            await self.repository.revoke(previous)

        credential = PostbackCredential(
            business_id=business_id,
            token_hash=hash_postback_token(plaintext),
            token_suffix=suffix,
            created_by_user_id=parse_id(user_id),
            created_at=now,
            last_success_at=last_success_at,
        )
        await self.repository.add(credential)
        await write_audit_log(
            self.db,
            user_id=parse_id(user_id),
            action="postback.credential_rotated" if previous else "postback.credential_created",
            resource_type="postback_credential",
            resource_id=str(credential.id),
            details={"token_suffix": suffix},
        )
        return PostbackTokenCreated(
            token=plaintext,
            token_suffix=suffix,
            created_at=now,
        )
