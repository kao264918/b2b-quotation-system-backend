import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from uuid import UUID
from typing import Optional


# ---------------------------------------------------------------------------
# Password strength policy
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$"
)
_PASSWORD_POLICY_MSG = (
    "Password must be 8-128 characters and contain at least "
    "one uppercase letter, one lowercase letter, and one digit."
)


def _validate_password_strength(v: str) -> str:
    if len(v) < PASSWORD_MIN_LENGTH:
        raise ValueError(_PASSWORD_POLICY_MSG)
    if len(v) > PASSWORD_MAX_LENGTH:
        raise ValueError(_PASSWORD_POLICY_MSG)
    if not _PASSWORD_PATTERN.match(v):
        raise ValueError(_PASSWORD_POLICY_MSG)
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class InviteRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    note: Optional[str] = None


class SetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class VerifyTokenResponse(BaseModel):
    valid: bool
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_verified: bool = False


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    role: Optional[str] = None
    status: Optional[str] = None
    access_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    status: str
    role: str
    is_superuser: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None
    is_superuser: Optional[bool] = None


class Token(BaseModel):
    access_token: str
    token_type: str
