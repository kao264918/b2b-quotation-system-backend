from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, field_validator
from typing import TYPE_CHECKING

from app.schemas.customer import Customer

# Reuse TaxSettingType from RFQ for consistency
TaxSettingType = Literal["taxable_5", "taxable_10", "non_taxable", "tax_exempt"]

if TYPE_CHECKING:
    pass

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

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v

class QuoteItem(QuoteItemBase):
    id: str
    quote_id: str
    rfq_item_id: Optional[str] = None
    catalog_item_id: Optional[str] = None
    snapshot_cost: Optional[Decimal] = None
    source_rfq_info: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class QuoteBase(BaseModel):
    title: str
    rfq_id: Optional[str] = None  # Optional for standalone quote creation
    customer_id: str
    status: str = "draft"
    
    # Tax setting (order-level, default 5%)
    tax_setting: TaxSettingType = "taxable_5"
    
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None

class QuoteCreate(QuoteBase):
    items: List[QuoteItemCreate]

class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    tax_setting: Optional[TaxSettingType] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    subtotal: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    total: Optional[Decimal] = None
    items: Optional[List[QuoteItemCreate]] = None

# Status update payloads
class QuoteStatusUpdate(BaseModel):
    """Update quotation status (draft/confirmed/closed/discarded)"""
    status: str

class QuoteAccountingStatusUpdate(BaseModel):
    """Update accounting status (unpaid/paid)"""
    accounting_status: str

# Audit log schema
class QuoteAuditLog(BaseModel):
    id: str
    action: str
    category: str  # 建立報價單, 更新項目內容, 更新稅務設定, 狀態變更, 會計狀態變更, 重啟報價
    timestamp: datetime
    actor: Optional[str] = None
    changes: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class Quote(QuoteBase):
    id: str
    quote_number: str
    accounting_status: Optional[str] = None
    version: int = 1
    cost_status: str = "ok"
    total_cost: Optional[Decimal] = None
    gross_profit_amount: Optional[Decimal] = None
    gross_profit_rate: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    items: List[QuoteItem] = []
    
    # Relationships
    customer: Optional["Customer"] = None
    
    model_config = ConfigDict(from_attributes=True)


class QuoteInternalKPI(BaseModel):
    range: Literal["month", "quarter", "all"]
    count: int
    total_revenue_excl_tax: Decimal
    total_cost: Decimal
    average_gross_profit_rate: Decimal
