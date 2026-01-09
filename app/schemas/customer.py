from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class CustomerBase(BaseModel):
    """Base schema with all Customer fields per CUSTOMER_FIELD_SPEC.md"""
    # Company Information
    company_name: str
    tax_id: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None

    # Address Information (required: address_line1, city, country)
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


class CustomerCreate(CustomerBase):
    """Schema for creating a Customer - all required fields must be provided"""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a Customer - all fields optional for partial update"""
    company_name: Optional[str] = None
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


class Customer(CustomerBase):
    """Full Customer schema for API responses"""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
