from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class CatalogItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit: str
    # reference_cost is INTENTIONALLY OMITTED from Base (Public)
    default_price: Optional[Decimal] = None
    tax_category: Optional[str] = None
    status: str = "active"

class CatalogItemCreate(CatalogItemBase):
    reference_cost: Optional[Decimal] = None # Allow setting cost on create

class CatalogItemUpdate(CatalogItemBase):
    name: Optional[str] = None
    unit: Optional[str] = None
    reference_cost: Optional[Decimal] = None

class CatalogItem(CatalogItemBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Internal Schema (includes cost)
class CatalogItemInternal(CatalogItem):
    reference_cost: Optional[Decimal] = None
