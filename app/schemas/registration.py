from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from app.models.registration_request import RegistrationStatus

class RegistrationRequestCreate(BaseModel):
    email: EmailStr
    full_name: str
    company_name: str
    note: Optional[str] = None

class RegistrationRequestResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    company_name: str
    note: Optional[str] = None
    status: RegistrationStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RegistrationApproveRequest(BaseModel):
    # Optional fields to override defaults when creating the user/company
    role: Optional[str] = "owner" # Default to owner for the first user of a company

class RegistrationRejectRequest(BaseModel):
    reason: str
