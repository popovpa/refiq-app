from datetime import datetime

from pydantic import BaseModel


class SdkCredentialStatus(BaseModel):
    configured: bool
    script_id: str | None = None
    created_at: datetime | None = None
    last_success_at: datetime | None = None
    integration_status: str
    sites_count: int = 0
    connected_sites: int = 0


class SdkCredentialCreated(BaseModel):
    script_id: str
    created_at: datetime
