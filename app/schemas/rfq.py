from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict
from .vendor_quote import VendorQuote


# ===== RFQ Item Schemas =====

class RFQItemBase(BaseModel):
    """Base schema for RFQ Item"""
    name: str
    type: Literal["product", "service", "output"]
    unit: str
    quantity: Decimal
    description: Optional[str] = None
    notes: Optional[str] = None
    
    # Customer-facing
    selling_price: Optional[Decimal] = None
    tax_category: Optional[str] = None
    
    # Output type specific
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    area_unit: Optional[Decimal] = None  # Read-only, calculated by backend


class RFQItemCreateFromCatalog(BaseModel):
    """Create RFQ Item from Catalog Item (Snapshot)"""
    catalog_item_id: str
    quantity: Decimal = Decimal("1")
    
    # Output type required fields
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    
    # Optional overrides
    unit_price_override: Optional[Decimal] = None
    description_override: Optional[str] = None


class RFQItemCreate(RFQItemBase):
    """Direct create (legacy, includes reference_cost)"""
    catalog_item_id: Optional[str] = None
    reference_cost: Optional[Decimal] = None


class RFQItemUpdate(BaseModel):
    """Update schema - allows modifying editable fields only"""
    name: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    tax_category: Optional[str] = None
    
    # Output type fields (triggers recalculation)
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    
    # Immutable fields (NOT in update schema):
    # - catalog_item_id
    # - source_item_no
    # - type
    # - area_unit (calculated)


class RFQItem(RFQItemBase):
    """Response schema include all fields"""
    id: str
    rfq_id: str
    catalog_item_id: Optional[str] = None
    source_item_no: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class RFQItemInternal(RFQItem):
    """Internal schema with reference_cost"""
    reference_cost: Optional[Decimal] = None
    vendor_quotes: List[VendorQuote] = []


# ===== RFQ Schemas =====

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
    """Internal RFQ with reference costs"""
    items: List[RFQItemInternal] = []

