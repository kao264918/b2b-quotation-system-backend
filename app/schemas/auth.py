from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

class InviteRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class SetPasswordRequest(BaseModel):
    token: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
