from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schema_version: int
    created_at: datetime
    event_type: str
    entity_type: str
    entity_id: int | None
    actor_type: str
    actor_user_id: int | None
    actor_admin_id: int | None
    actor_business_id: int | None
    actor_partner_id: int | None
    source_service: str
    source_operation: str | None
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    reason: str | None
    changes: dict | None
    metadata: dict | None = Field(validation_alias="metadata_")
