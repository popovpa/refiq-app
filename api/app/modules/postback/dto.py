from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PostbackRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rqcid: str
    amount: float | None = None
    currency: str | None = None


class PostbackAccepted(BaseModel):
    status: str = "accepted"


class PostbackCredentialStatus(BaseModel):
    configured: bool
    token_suffix: str | None = None
    created_at: datetime | None = None
    last_success_at: datetime | None = None
    token_status: str | None = None
    integration_status: str


class PostbackTokenCreated(BaseModel):
    token: str
    token_suffix: str
    created_at: datetime
