from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from .vendor_quote import VendorQuote

class RFQItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    quantity: Decimal
    unit: str
    catalog_item_id: Optional[str] = None
    
    # Customer-facing
    selling_price: Optional[Decimal] = None
    tax_category: Optional[str] = None
    notes: Optional[str] = None
    
    # ❌ Reference Cost is intentionally omitted from Base

class RFQItemCreate(RFQItemBase):
    reference_cost: Optional[Decimal] = None

class RFQItemUpdate(RFQItemBase):
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None

class RFQItem(RFQItemBase):
    id: str
    rfq_id: str
    
    model_config = ConfigDict(from_attributes=True)

class RFQBase(BaseModel):
    title: str
    customer_id: str
    description: Optional[str] = None
    status: str = "draft"

class RFQCreate(RFQBase):
    items: List[RFQItemCreate] = []

class RFQUpdate(RFQBase):
    title: Optional[str] = None
    customer_id: Optional[str] = None
    items: Optional[List[RFQItemCreate]] = None

class RFQ(RFQBase):
    id: str
    created_at: datetime
    updated_at: datetime
    items: List[RFQItem] = []
    
    model_config = ConfigDict(from_attributes=True)

class RFQDetailInternal(RFQ):
    items: List[RFQItem] # Should ideally return items with reference_cost
    # But since RFQItem above excluded cost, we might need a separate RFQItemInternal
    pass

class RFQItemInternal(RFQItem):
    reference_cost: Optional[Decimal] = None
    vendor_quotes: List[VendorQuote] = []
