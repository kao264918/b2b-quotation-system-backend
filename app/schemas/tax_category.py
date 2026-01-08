from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class TaxCategoryBase(BaseModel):
    name: str
    code: str
    rate: Decimal
    description: Optional[str] = None
    status: str = "active"

class TaxCategoryCreate(TaxCategoryBase):
    pass

class TaxCategoryUpdate(TaxCategoryBase):
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    code: Optional[str] = None

class TaxCategory(TaxCategoryBase):
    id: str
    
    model_config = ConfigDict(from_attributes=True)
