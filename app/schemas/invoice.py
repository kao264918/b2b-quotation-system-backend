from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class InvoiceItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    quantity: Decimal
    unit: str
    unit_price: Decimal
    
    tax_category_name: str
    tax_rate: Decimal
    
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    
    line_total: Decimal  # Deprecated

class InvoiceItemCreate(InvoiceItemBase):
    quote_item_id: Optional[str] = None

class InvoiceItem(InvoiceItemBase):
    id: str
    invoice_id: str
    quote_item_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class InvoiceBase(BaseModel):
    quote_id: str
    customer_id: str
    status: str = "draft"
    accounting_status: Optional[str] = None  # unpaid, paid
    
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    
    notes: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None

class InvoiceCreate(InvoiceBase):
    invoice_number: Optional[str] = None  # Auto-generated if not provided
    items: List[InvoiceItemCreate]

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    accounting_status: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None

# Status update payloads
class InvoiceStatusUpdate(BaseModel):
    """Update invoice status (draft → issued)"""
    status: str

class InvoiceAccountingStatusUpdate(BaseModel):
    """Update accounting status (unpaid/paid)"""
    accounting_status: str

# Create from quote payload
class InvoiceFromQuoteRequest(BaseModel):
    """Request to create invoice from a confirmed quote"""
    quote_id: str

# Customer embedded schema for response
class InvoiceCustomer(BaseModel):
    id: str
    company_name: str
    tax_id: Optional[str] = None
    company_email: Optional[str] = None
    contact_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class Invoice(InvoiceBase):
    id: str
    invoice_number: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    items: List[InvoiceItem] = []
    
    # Embedded customer info
    customer: Optional[InvoiceCustomer] = None
    
    model_config = ConfigDict(from_attributes=True)
