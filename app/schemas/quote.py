from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class QuoteItemBase(BaseModel):
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
    
    line_total: Decimal # Deprecated

class QuoteItemCreate(QuoteItemBase):
    rfq_item_id: Optional[str] = None
    catalog_item_id: Optional[str] = None

class QuoteItem(QuoteItemBase):
    id: str
    quote_id: str
    rfq_item_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class QuoteBase(BaseModel):
    title: str
    rfq_id: str
    customer_id: str
    status: str = "draft"
    
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None

class QuoteCreate(QuoteBase):
    items: List[QuoteItemCreate]

class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = None # Restricted transitions

class Quote(QuoteBase):
    id: str
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    items: List[QuoteItem] = []
    
    model_config = ConfigDict(from_attributes=True)
