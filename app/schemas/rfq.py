"""
RFQ Schemas (Pydantic) - API Request/Response Models

Separates:
- Create/Update schemas (input validation)
- Response schemas (output serialization)
- Internal schemas (with sensitive data, not exposed to API)
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Enums (mirroring SQLAlchemy enums for API documentation)
# ============================================================================

RFQStatusType = Literal["draft", "vendor_quoting", "finalized", "closed", "discarded"]
AccountingStatusType = Literal["unfulfilled", "fulfilled", "paid"]
TaxSettingType = Literal["taxable_5", "taxable_10", "non_taxable", "tax_exempt"]
ItemType = Literal["product", "service", "output"]


# ============================================================================
# RFQ Item Schemas
# ============================================================================

class RFQItemBase(BaseModel):
    """Base schema for RFQ Item - shared fields"""
    name: str = Field(..., min_length=1, max_length=255)
    item_type: ItemType
    description: Optional[str] = None
    spec_notes: Optional[str] = None
    quantity: Decimal = Field(default=Decimal("1"), ge=0)
    unit: str = Field(default="pcs", max_length=20)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Dimension fields (for output type)
    length_cm: Optional[Decimal] = Field(default=None, ge=0)
    width_cm: Optional[Decimal] = Field(default=None, ge=0)


class RFQItemCreate(RFQItemBase):
    """Create a new item directly"""
    id: Optional[str] = None  # Temporary ID from frontend for validation mapping
    catalog_item_id: Optional[str] = None
    sort_order: int = 0


class RFQItemFromCatalog(BaseModel):
    """Create item by copying from catalog"""
    catalog_item_id: str
    quantity: Decimal = Field(default=Decimal("1"), ge=0)
    
    # Optional dimension overrides (for output type)
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    
    # Optional price/description overrides
    unit_price_override: Optional[Decimal] = None
    spec_notes: Optional[str] = None
    sort_order: int = 0


class RFQItemUpdate(BaseModel):
    """Update existing item - only editable fields"""
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    spec_notes: Optional[str] = None
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=20)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    length_cm: Optional[Decimal] = Field(default=None, ge=0)
    width_cm: Optional[Decimal] = Field(default=None, ge=0)
    sort_order: Optional[int] = None


class RFQItemResponse(RFQItemBase):
    """Response schema - includes computed fields"""
    id: str
    rfq_version_id: str
    catalog_item_id: Optional[str] = None
    source_item_no: Optional[str] = None
    sort_order: int
    
    # Computed by backend
    area_unit: Optional[Decimal] = None
    line_subtotal: Decimal
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RFQ Version Schemas
# ============================================================================

class VendorSnapshot(BaseModel):
    """Vendor data snapshot stored in version"""
    id: str
    name: str
    company_name: str
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None


class RFQVersionBase(BaseModel):
    """Base schema for RFQ Version"""
    project_name: str = Field(..., min_length=1, max_length=255)
    required_date: Optional[datetime] = None
    tax_setting: TaxSettingType = "non_taxable"
    currency: str = Field(default="TWD", max_length=10)
    notes: Optional[str] = None


class RFQVersionCreate(RFQVersionBase):
    """Create a new version - includes items"""
    items: List[RFQItemCreate] = []


class RFQVersionResponse(RFQVersionBase):
    """Response schema for version"""
    id: str
    rfq_id: str
    version_number: int
    vendor_snapshot: VendorSnapshot
    
    # Computed totals (backend-authoritative)
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    
    # Audit
    created_at: datetime
    created_by: Optional[str] = None
    
    # Line items
    items: List[RFQItemResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class RFQVersionSummary(BaseModel):
    """Lightweight version info for list/dropdown"""
    id: str
    version_number: int
    total_amount: Decimal
    created_at: datetime
    notes: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RFQ Master Schemas
# ============================================================================

class RFQBase(BaseModel):
    """Base schema for RFQ master"""
    project_name: str = Field(..., min_length=1, max_length=255)
    vendor_id: str


class RFQCreate(RFQBase):
    """Create new RFQ - includes first version data"""
    required_date: Optional[datetime] = None
    tax_setting: TaxSettingType = "non_taxable"
    notes: Optional[str] = None
    items: List[RFQItemCreate] = []


class RFQUpdate(BaseModel):
    """Update RFQ - creates new version"""
    project_name: Optional[str] = Field(default=None, max_length=255)
    required_date: Optional[datetime] = None
    tax_setting: Optional[TaxSettingType] = None
    notes: Optional[str] = None  # Revision notes (required for non-first versions)
    items: Optional[List[RFQItemCreate]] = None


class RFQStatusUpdate(BaseModel):
    """Update workflow status only"""
    status: RFQStatusType


class RFQAccountingStatusUpdate(BaseModel):
    """Update accounting status only (independent of workflow)"""
    accounting_status: AccountingStatusType


class RFQSelectVersion(BaseModel):
    """Select a version as final"""
    version_id: str


class RFQResponse(RFQBase):
    """Response schema for RFQ master"""
    id: str
    rfq_no: str
    status: RFQStatusType
    accounting_status: AccountingStatusType
    
    # Version pointers
    current_version_id: Optional[str] = None
    selected_version_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RFQDetailResponse(RFQResponse):
    """Full RFQ with current version data"""
    current_version: Optional[RFQVersionResponse] = None
    versions: List[RFQVersionSummary] = []


class RFQListItemResponse(BaseModel):
    """Lightweight RFQ info for list view"""
    id: str
    rfq_no: str
    project_name: str
    vendor_name: str  # Denormalized from vendor
    status: RFQStatusType
    accounting_status: AccountingStatusType
    
    # From current version
    subtotal: Decimal
    total_amount: Decimal
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RFQListResponse(BaseModel):
    """Paginated list response"""
    items: List[RFQListItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

# Aliases for consistent naming in __init__.py
RFQ = RFQResponse
RFQItem = RFQItemResponse
RFQItemCreateFromCatalog = RFQItemFromCatalog
