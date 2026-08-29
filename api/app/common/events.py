from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession


async def emit_event(
    db: AsyncSession,
    event_type: str,
    payload: dict,
    aggregate_type: str | None = None,
    aggregate_id: str | int | None = None,
):
    from app.modules.system.models import OutboxEvent
    event = OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id) if aggregate_id is not None else None,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
