from typing import List
from pydantic import BaseModel, ConfigDict

class QuoteTemplateBase(BaseModel):
    name: str
    type: str = "system"
    formats: List[str]
    is_default: bool = False
    status: str = "active"

class QuoteTemplate(QuoteTemplateBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

class InvoiceTemplateBase(BaseModel):
    name: str
    type: str = "system"
    formats: List[str]
    is_default: bool = False
    status: str = "active"

class InvoiceTemplate(InvoiceTemplateBase):
    id: str
    model_config = ConfigDict(from_attributes=True)
