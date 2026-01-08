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
    
    line_total: Decimal

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
    
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    
    issued_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate]

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    due_date: Optional[datetime] = None

class Invoice(InvoiceBase):
    id: str
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItem] = []
    
    model_config = ConfigDict(from_attributes=True)
