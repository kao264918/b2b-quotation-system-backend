from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# Contact
class VendorContactBase(BaseModel):
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool = False

class VendorContactCreate(VendorContactBase):
    pass

class VendorContact(VendorContactBase):
    id: str
    vendor_id: str
    model_config = ConfigDict(from_attributes=True)

# Vendor
class VendorBase(BaseModel):
    name: str
    company_name: str
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    default_payment_terms: Optional[str] = None
    default_currency: Optional[str] = "TWD"
    status: str = "active"
    notes: Optional[str] = None

class VendorCreate(VendorBase):
    contacts: List[VendorContactCreate] = []

class VendorUpdate(VendorBase):
    name: Optional[str] = None
    company_name: Optional[str] = None
    contacts: Optional[List[VendorContactCreate]] = None

class Vendor(VendorBase):
    id: str
    created_at: datetime
    updated_at: datetime
    contacts: List[VendorContact] = []
    
    model_config = ConfigDict(from_attributes=True)
