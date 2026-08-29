from datetime import datetime

from pydantic import BaseModel, Field


class SiteCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    name: str | None = Field(default=None, max_length=255)


class SiteUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class SiteResponse(BaseModel):
    id: int
    business_id: int
    name: str
    domain: str
    status: str
    display_status: str
    site_key: str
    sdk_status: str
    last_success_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    disabled_at: datetime | None = None
    can_delete: bool
