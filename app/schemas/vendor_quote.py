from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class VendorQuoteBase(BaseModel):
    unit_cost: Decimal
    currency: str = "TWD"
    moq: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    shipping_cost: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    valid_until: Optional[datetime] = None
    is_selected: bool = False
    notes: Optional[str] = None

class VendorQuoteCreate(VendorQuoteBase):
    rfq_item_id: str
    vendor_id: str

class VendorQuoteUpdate(VendorQuoteBase):
    unit_cost: Optional[Decimal] = None

class VendorQuote(VendorQuoteBase):
    id: str
    rfq_item_id: str
    vendor_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
