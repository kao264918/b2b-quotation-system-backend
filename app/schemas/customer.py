from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class CustomerBase(BaseModel):
    """Base schema with all Customer fields per CUSTOMER_FIELD_SPEC.md"""
    # Company Information
    company_name: str
    company_email: Optional[str] = None
    tax_id: str  # Required, minimum 8 characters
    industry: Optional[str] = None
    website: Optional[str] = None

    @field_validator('tax_id')
    @classmethod
    def validate_tax_id(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('統一編號至少需要 8 碼')
        return v

    # Address Information
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    postal_code: Optional[str] = None
    country: str

    # Primary Contact (required: contact_name, contact_email)
    contact_name: str
    contact_email: str
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None

    # Billing & Internal
    billing_email: Optional[str] = None
    notes: Optional[str] = None

    status: str = "active"
    roles: List[str] = ["customer"]

    # Vendor specific fields
    default_currency: Optional[str] = "TWD"
    default_payment_terms: Optional[str] = None


class CustomerCreate(CustomerBase):
    """Schema for creating a Customer - all required fields must be provided"""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a Customer - all fields optional for partial update"""
    company_name: Optional[str] = None
    company_email: Optional[str] = None
    tax_id: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None

    billing_email: Optional[str] = None
    notes: Optional[str] = None

    status: Optional[str] = None
    roles: Optional[List[str]] = None
    
    default_currency: Optional[str] = None
    default_payment_terms: Optional[str] = None

    @field_validator('tax_id')
    @classmethod
    def validate_tax_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError('統一編號至少需要 8 碼')
        return v


class Customer(CustomerBase):
    """Full Customer schema for API responses"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    """Schema for paginated customer list response"""
    items: List["Customer"]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)
