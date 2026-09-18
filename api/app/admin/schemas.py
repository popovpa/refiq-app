from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.common.enums import LegalVerificationRejectReason


class ActionReason(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class LegalEntityVerifyRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class LegalEntityRejectRequest(BaseModel):
    reason_code: LegalVerificationRejectReason
    comment: str | None = Field(default=None, max_length=2000)


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AdminSessionResponse(BaseModel):
    id: int
    email: str
    role: str
    permissions: list[str]
    status: str
    last_login_at: datetime | None = None


class CursorPage(BaseModel):
    items: list
    next_cursor: str | None = None
    has_more: bool = False


class OffsetPage(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
