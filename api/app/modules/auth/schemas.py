from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterResponse(BaseModel):
    status: str
    message: str


class ConfirmEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class ConfirmEmailResponse(BaseModel):
    status: str
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    status: str
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    status: str
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str | None
    last_name: str | None
    avatar_url: str | None
    phone: str | None
    timezone: str
    language: str
    email_verified_at: str | None
    status: str
    roles: list[dict]
    created_at: str | None = None


class SessionResponse(BaseModel):
    user: UserResponse
    active_role: str | None
    active_business_id: str | None
    business_name: str | None = None
    partner_name: str | None = None

    @field_validator("active_business_id", mode="before")
    @classmethod
    def coerce_business_id(cls, value):
        if value is None or value == "":
            return None
        return str(value)
