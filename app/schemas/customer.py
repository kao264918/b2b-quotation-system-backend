from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# Contact
class CustomerContactBase(BaseModel):
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool = False

class CustomerContactCreate(CustomerContactBase):
    pass

class CustomerContact(CustomerContactBase):
    id: str
    customer_id: str
    model_config = ConfigDict(from_attributes=True)

# Customer
class CustomerBase(BaseModel):
    name: str
    company_name: str
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    default_payment_terms: Optional[str] = None
    status: str = "active"

class CustomerCreate(CustomerBase):
    contacts: List[CustomerContactCreate] = []

class CustomerUpdate(CustomerBase):
    name: Optional[str] = None
    company_name: Optional[str] = None
    contacts: Optional[List[CustomerContactCreate]] = None

class Customer(CustomerBase):
    id: str
    created_at: datetime
    updated_at: datetime
    contacts: List[CustomerContact] = []
    
    model_config = ConfigDict(from_attributes=True)
