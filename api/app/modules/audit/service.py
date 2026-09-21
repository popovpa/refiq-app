from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.context import AuditContext
from app.modules.audit.models import AuditEvent
from app.modules.audit.sanitizer import sanitize_payload


class AuditService:
    async def record(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        context: AuditContext,
        changes: dict | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
        source_operation: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            schema_version=1,
            created_at=datetime.now(timezone.utc),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=context.actor_type,
            actor_user_id=context.user_id,
            actor_admin_id=context.admin_id,
            actor_business_id=context.business_id,
            actor_partner_id=context.partner_id,
            source_service=context.source_service,
            source_operation=source_operation,
            request_id=context.request_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            reason=reason,
            changes=sanitize_payload(changes),
            metadata_=sanitize_payload(metadata),
        )
        session.add(event)
        await session.flush()
        return event


audit_service = AuditService()
